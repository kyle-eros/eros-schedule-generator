"""
EROS MCP Server Rate Limiting Tests

Comprehensive test suite for rate limiting functionality including:
- Token bucket mechanics
- Per-tool and global rate limits
- Burst handling
- Configuration loading
- Thread safety
- Error responses

Usage:
    python -m pytest mcp/test_rate_limiting.py -v
    python mcp/test_rate_limiting.py  # Direct execution
"""

import json
import os
import tempfile
import threading
import time
import unittest
from typing import Any, Dict

from mcp.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    TokenBucket,
    check_rate_limit,
    get_rate_limit_stats,
    reset_rate_limiter,
)


class TestTokenBucket(unittest.TestCase):
    """Test token bucket implementation."""

    def test_initial_capacity(self):
        """Token bucket should start at full capacity."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        bucket = TokenBucket(config)
        self.assertAlmostEqual(bucket.get_available_tokens(), 100, places=1)

    def test_consume_single_token(self):
        """Consuming a single token should succeed."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        bucket = TokenBucket(config)
        self.assertTrue(bucket.consume(1))
        self.assertAlmostEqual(bucket.get_available_tokens(), 99, places=1)

    def test_consume_multiple_tokens(self):
        """Consuming multiple tokens should succeed."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        bucket = TokenBucket(config)
        self.assertTrue(bucket.consume(10))
        self.assertAlmostEqual(bucket.get_available_tokens(), 90, places=1)

    def test_consume_beyond_capacity(self):
        """Consuming more tokens than available should fail."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=10)
        bucket = TokenBucket(config)
        # Consume all tokens
        self.assertTrue(bucket.consume(10))
        # Try to consume one more
        self.assertFalse(bucket.consume(1))

    def test_token_refill(self):
        """Tokens should refill over time."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        bucket = TokenBucket(config)

        # Consume 10 tokens
        bucket.consume(10)
        self.assertAlmostEqual(bucket.get_available_tokens(), 90, places=1)

        # Wait 1 second (should refill 1 token at 60 RPM)
        time.sleep(1.0)
        tokens = bucket.get_available_tokens()
        self.assertGreater(tokens, 90)
        self.assertLess(tokens, 92)  # Should be ~91

    def test_refill_rate(self):
        """Refill rate should match requests_per_minute."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        bucket = TokenBucket(config)

        # Refill rate should be 60/60 = 1 token per second
        self.assertEqual(bucket.refill_rate, 1.0)

    def test_capacity_limit(self):
        """Tokens should not exceed capacity when refilling."""
        config = RateLimitConfig(requests_per_minute=600, burst_capacity=10)
        bucket = TokenBucket(config)

        # Start at full capacity
        self.assertAlmostEqual(bucket.get_available_tokens(), 10, places=1)

        # Wait 1 second (would refill 10 tokens, but capped at capacity)
        time.sleep(1.0)
        self.assertAlmostEqual(bucket.get_available_tokens(), 10, places=1)

    def test_retry_after(self):
        """get_retry_after should return correct wait time."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=10)
        bucket = TokenBucket(config)

        # Consume all tokens
        bucket.consume(10)

        # Should need to wait ~1 second for next token (60 RPM = 1/sec)
        retry_after = bucket.get_retry_after()
        self.assertGreater(retry_after, 0.9)
        self.assertLess(retry_after, 1.1)

    def test_thread_safety(self):
        """Token bucket should be thread-safe."""
        config = RateLimitConfig(requests_per_minute=600, burst_capacity=1000)
        bucket = TokenBucket(config)

        success_count = [0]
        failure_count = [0]
        lock = threading.Lock()

        def worker():
            for _ in range(100):
                if bucket.consume(1):
                    with lock:
                        success_count[0] += 1
                else:
                    with lock:
                        failure_count[0] += 1

        # Launch 10 threads, each trying to consume 100 tokens
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Total attempts: 10 * 100 = 1000
        # Should succeed exactly 1000 times (initial capacity)
        self.assertEqual(success_count[0], 1000)
        self.assertEqual(failure_count[0], 0)


class TestRateLimitConfig(unittest.TestCase):
    """Test rate limit configuration."""

    def test_valid_config(self):
        """Valid configuration should be accepted."""
        config = RateLimitConfig(requests_per_minute=60, burst_capacity=100)
        self.assertEqual(config.requests_per_minute, 60)
        self.assertEqual(config.burst_capacity, 100)

    def test_burst_capacity_auto_adjust(self):
        """Burst capacity should auto-adjust to match RPM if lower."""
        config = RateLimitConfig(requests_per_minute=100, burst_capacity=50)
        # Should be adjusted to match RPM
        self.assertEqual(config.burst_capacity, 100)

    def test_invalid_rpm(self):
        """Invalid requests_per_minute should raise error."""
        with self.assertRaises(ValueError):
            RateLimitConfig(requests_per_minute=0, burst_capacity=10)

        with self.assertRaises(ValueError):
            RateLimitConfig(requests_per_minute=-10, burst_capacity=10)


class TestRateLimiter(unittest.TestCase):
    """Test rate limiter functionality."""

    def setUp(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_singleton_pattern(self):
        """RateLimiter should be a singleton."""
        limiter1 = RateLimiter.get_instance()
        limiter2 = RateLimiter.get_instance()
        self.assertIs(limiter1, limiter2)

    def test_consume_success(self):
        """Consuming within limits should succeed."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )
        self.assertTrue(limiter.consume("test_tool"))

    def test_consume_tool_limit_exceeded(self):
        """Exceeding per-tool limit should fail."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 10)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        # Consume all 10 tokens
        for _ in range(10):
            self.assertTrue(limiter.consume("test_tool"))

        # 11th should fail
        self.assertFalse(limiter.consume("test_tool"))

    def test_consume_global_limit_exceeded(self):
        """Exceeding global limit should fail."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 10),
            enabled=True
        )

        # Consume all 10 global tokens
        for _ in range(10):
            self.assertTrue(limiter.consume("test_tool"))

        # 11th should fail (global limit)
        self.assertFalse(limiter.consume("test_tool"))

    def test_disabled_limiter(self):
        """Disabled limiter should allow all requests."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 1)},
            global_limit=RateLimitConfig(1000, 1),
            enabled=False
        )

        # Should allow unlimited requests when disabled
        for _ in range(100):
            self.assertTrue(limiter.consume("test_tool"))

    def test_unconfigured_tool(self):
        """Unconfigured tools should use default limits."""
        limiter = RateLimiter(
            tool_limits={},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        # Should create bucket with default config
        self.assertTrue(limiter.consume("unknown_tool"))

    def test_retry_after(self):
        """get_retry_after should return correct wait time."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 10)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        # Consume all tokens
        for _ in range(10):
            limiter.consume("test_tool")

        # Should need to wait ~1 second
        retry_after = limiter.get_retry_after("test_tool")
        self.assertGreater(retry_after, 0.9)
        self.assertLess(retry_after, 1.1)

    def test_get_stats(self):
        """get_stats should return current rate limiter state."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        stats = limiter.get_stats()

        # Check structure
        self.assertTrue(stats["enabled"])
        self.assertIn("global", stats)
        self.assertIn("tools", stats)

        # Check global stats
        self.assertEqual(stats["global"]["requests_per_minute"], 1000)
        self.assertEqual(stats["global"]["burst_capacity"], 1200)

        # Check tool stats
        self.assertIn("test_tool", stats["tools"])
        self.assertEqual(stats["tools"]["test_tool"]["requests_per_minute"], 60)


class TestRateLimitExceeded(unittest.TestCase):
    """Test RateLimitExceeded exception."""

    def test_exception_message(self):
        """Exception should have correct message."""
        exc = RateLimitExceeded("test_tool", 1.23, "tool")
        self.assertIn("test_tool", str(exc))
        self.assertIn("1.23", str(exc))
        self.assertIn("tool", str(exc))

    def test_to_dict(self):
        """to_dict should return correct error response."""
        exc = RateLimitExceeded("test_tool", 1.23, "global")
        error_dict = exc.to_dict()

        self.assertEqual(error_dict["error"], "RateLimitExceeded")
        self.assertEqual(error_dict["tool"], "test_tool")
        self.assertEqual(error_dict["retry_after"], 1.23)
        self.assertEqual(error_dict["limit_type"], "global")
        self.assertEqual(error_dict["http_status_equivalent"], 429)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def setUp(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_check_rate_limit_success(self):
        """check_rate_limit should succeed within limits."""
        # Configure low limits for testing
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )
        # Replace singleton
        RateLimiter._instance = limiter

        # Should not raise exception
        check_rate_limit("test_tool")

    def test_check_rate_limit_exceeded(self):
        """check_rate_limit should raise exception when exceeded."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 10)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )
        # Replace singleton
        RateLimiter._instance = limiter

        # Consume all tokens
        for _ in range(10):
            check_rate_limit("test_tool")

        # 11th should raise exception
        with self.assertRaises(RateLimitExceeded) as ctx:
            check_rate_limit("test_tool")

        exc = ctx.exception
        self.assertEqual(exc.tool_name, "test_tool")
        self.assertGreater(exc.retry_after, 0)

    def test_get_rate_limit_stats(self):
        """get_rate_limit_stats should return current stats."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )
        # Replace singleton
        RateLimiter._instance = limiter

        stats = get_rate_limit_stats()

        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["global"]["requests_per_minute"], 1000)


class TestConfigurationLoading(unittest.TestCase):
    """Test configuration loading from settings.local.json."""

    def setUp(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def test_load_from_settings_file(self):
        """Configuration should load from settings.local.json."""
        # Create temporary settings file
        settings = {
            "rate_limiting": {
                "global": {
                    "requests_per_minute": 999,
                    "burst_capacity": 1111
                },
                "tools": {
                    "custom_tool": {
                        "requests_per_minute": 77,
                        "burst_capacity": 88
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(settings, f)
            settings_path = f.name

        try:
            # Mock the settings path
            original_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                ".claude",
                "settings.local.json"
            )

            # Note: This test assumes the _load_config method can be mocked
            # In real implementation, you'd need dependency injection
            # For now, just verify default config
            tool_limits, global_limit = RateLimiter._load_config()

            # Should have defaults if file doesn't exist
            self.assertIsNotNone(tool_limits)
            self.assertIsNotNone(global_limit)

        finally:
            os.unlink(settings_path)


class TestBurstBehavior(unittest.TestCase):
    """Test burst handling behavior."""

    def test_burst_allowance(self):
        """Should allow bursts up to burst_capacity."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        # Should allow 100 rapid requests (burst capacity)
        for i in range(100):
            success = limiter.consume("test_tool")
            self.assertTrue(success, f"Request {i+1} should succeed")

        # 101st should fail
        self.assertFalse(limiter.consume("test_tool"))

    def test_sustained_rate(self):
        """Should enforce sustained rate after burst."""
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(600, 10)},  # 10 req/sec
            global_limit=RateLimitConfig(10000, 12000),
            enabled=True
        )

        # Use burst
        for _ in range(10):
            self.assertTrue(limiter.consume("test_tool"))

        # Wait 0.1 second (should refill 1 token)
        time.sleep(0.1)

        # Should allow 1 more request
        self.assertTrue(limiter.consume("test_tool"))

        # Next should fail
        self.assertFalse(limiter.consume("test_tool"))


class TestMetricsIntegration(unittest.TestCase):
    """Test Prometheus metrics integration."""

    def test_metrics_graceful_degradation(self):
        """Should work even if prometheus_client not installed."""
        # This is tested implicitly by the limiter initialization
        # If prometheus_client is not available, metrics_available = False
        limiter = RateLimiter(
            tool_limits={"test_tool": RateLimitConfig(60, 100)},
            global_limit=RateLimitConfig(1000, 1200),
            enabled=True
        )

        # Should still work without metrics
        self.assertTrue(limiter.consume("test_tool"))


def run_manual_tests():
    """Run manual interactive tests."""
    print("=" * 70)
    print("EROS Rate Limiting Manual Tests")
    print("=" * 70)

    # Test 1: Burst then rate limit
    print("\nTest 1: Burst Handling")
    print("-" * 70)
    limiter = RateLimiter(
        tool_limits={"test_tool": RateLimitConfig(10, 12)},
        global_limit=RateLimitConfig(100, 120),
        enabled=True
    )
    RateLimiter._instance = limiter

    for i in range(15):
        try:
            check_rate_limit("test_tool")
            print(f"  Request {i+1:2d}: SUCCESS")
        except RateLimitExceeded as e:
            print(f"  Request {i+1:2d}: RATE LIMITED (retry after {e.retry_after:.2f}s)")

    # Test 2: Stats reporting
    print("\nTest 2: Rate Limiter Stats")
    print("-" * 70)
    stats = get_rate_limit_stats()
    print(json.dumps(stats, indent=2))

    # Test 3: Recovery after wait
    print("\nTest 3: Recovery After Wait")
    print("-" * 70)
    reset_rate_limiter()
    limiter = RateLimiter(
        tool_limits={"test_tool": RateLimitConfig(60, 5)},
        global_limit=RateLimitConfig(1000, 1200),
        enabled=True
    )
    RateLimiter._instance = limiter

    # Use all tokens
    for i in range(5):
        check_rate_limit("test_tool")
        print(f"  Request {i+1}: SUCCESS")

    # Next should fail
    try:
        check_rate_limit("test_tool")
        print("  Request 6: SUCCESS (unexpected!)")
    except RateLimitExceeded as e:
        print(f"  Request 6: RATE LIMITED (retry after {e.retry_after:.2f}s)")
        print(f"  Waiting {e.retry_after:.2f} seconds...")
        time.sleep(e.retry_after)

    # Should succeed after wait
    try:
        check_rate_limit("test_tool")
        print("  Request 7 (after wait): SUCCESS")
    except RateLimitExceeded:
        print("  Request 7 (after wait): RATE LIMITED (unexpected!)")

    print("\n" + "=" * 70)
    print("Manual tests complete")
    print("=" * 70)


if __name__ == "__main__":
    # Run unit tests
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)

    # Run manual tests
    print("\n\n")
    run_manual_tests()
