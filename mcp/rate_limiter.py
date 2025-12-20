"""
EROS MCP Server Rate Limiting

Implements token bucket rate limiting for MCP tools to prevent abuse,
ensure fair resource allocation, and protect database integrity.

Features:
- Per-tool rate limits (requests/minute)
- Global rate limit (total requests/minute)
- Token bucket algorithm (allows bursts)
- Configurable via environment variables and settings.local.json
- Prometheus metrics integration
- Graceful degradation (can be disabled)

Architecture:
- Two-tier throttling: per-tool + global limits
- Token bucket: refills at steady rate, allows bursts up to capacity
- Redis-compatible (future): designed for distributed rate limiting

Usage:
    from mcp.rate_limiter import RateLimiter, check_rate_limit

    # In decorator or wrapper
    check_rate_limit("get_creator_profile")

    # Manual usage
    limiter = RateLimiter.get_instance()
    if not limiter.consume("my_tool"):
        raise RateLimitExceeded("Rate limit exceeded")
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("eros_db_server.rate_limiter")


# =============================================================================
# Rate Limit Configuration
# =============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tool."""

    requests_per_minute: int
    burst_capacity: int  # Max tokens in bucket (allows bursts)

    def __post_init__(self):
        """Validate configuration."""
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if self.burst_capacity < self.requests_per_minute:
            # Burst capacity should be at least equal to RPM
            self.burst_capacity = self.requests_per_minute


# Default per-tool rate limits (requests/minute)
DEFAULT_TOOL_LIMITS: Dict[str, RateLimitConfig] = {
    # High-frequency reads (100 RPM)
    "get_top_captions": RateLimitConfig(100, 120),
    "get_send_type_captions": RateLimitConfig(100, 120),
    "get_vault_availability": RateLimitConfig(100, 120),

    # Medium-frequency reads (50 RPM)
    "get_creator_profile": RateLimitConfig(50, 60),
    "get_volume_config": RateLimitConfig(50, 60),
    "get_performance_trends": RateLimitConfig(50, 60),
    "get_content_type_rankings": RateLimitConfig(50, 60),
    "get_best_timing": RateLimitConfig(50, 60),
    "get_persona_profile": RateLimitConfig(50, 60),
    "get_send_types": RateLimitConfig(50, 60),
    "get_send_type_details": RateLimitConfig(50, 60),
    "get_channels": RateLimitConfig(50, 60),
    "get_active_creators": RateLimitConfig(50, 60),

    # Medium-frequency analytics (40 RPM)
    "get_caption_predictions": RateLimitConfig(40, 50),
    "get_churn_risk_scores": RateLimitConfig(40, 50),
    "get_win_back_candidates": RateLimitConfig(40, 50),
    "get_attention_metrics": RateLimitConfig(40, 50),
    "get_caption_attention_scores": RateLimitConfig(40, 50),
    "get_active_experiments": RateLimitConfig(40, 50),
    "get_active_volume_triggers": RateLimitConfig(40, 50),
    "get_prediction_weights": RateLimitConfig(40, 50),
    "get_content_type_earnings_ranking": RateLimitConfig(40, 50),
    "get_top_captions_by_earnings": RateLimitConfig(40, 50),

    # Low-frequency reads (30 RPM)
    "validate_caption_structure": RateLimitConfig(30, 40),
    "execute_query": RateLimitConfig(30, 40),

    # Write operations - medium rate (20 RPM)
    "save_volume_triggers": RateLimitConfig(20, 25),
    "save_caption_prediction": RateLimitConfig(20, 25),
    "record_prediction_outcome": RateLimitConfig(20, 25),
    "save_experiment_results": RateLimitConfig(20, 25),
    "update_experiment_allocation": RateLimitConfig(20, 25),

    # Write operations - low rate (10 RPM)
    "save_schedule": RateLimitConfig(10, 12),

    # Critical writes - very low rate (5 RPM)
    "update_prediction_weights": RateLimitConfig(5, 6),
}

# Global rate limit (total requests/minute across all tools)
# Default: 500 RPM with burst capacity of 600
DEFAULT_GLOBAL_LIMIT = RateLimitConfig(500, 600)

# Default rate limit for tools not explicitly configured
DEFAULT_TOOL_LIMIT = RateLimitConfig(30, 40)


# =============================================================================
# Token Bucket Implementation
# =============================================================================

class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursts up to capacity while maintaining sustained rate.
    Tokens refill at steady rate (requests_per_minute / 60 per second).

    Thread-safe implementation using locks.
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize token bucket.

        Args:
            config: Rate limit configuration.
        """
        self.capacity = config.burst_capacity
        self.refill_rate = config.requests_per_minute / 60.0  # tokens per second
        self.tokens = float(config.burst_capacity)  # Start full
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on time elapsed (internal, assumes lock held)."""
        now = time.monotonic()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1).

        Returns:
            True if tokens were consumed, False if insufficient tokens.
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.

        Returns:
            Number of tokens currently available.
        """
        with self.lock:
            self._refill()
            return self.tokens

    def get_retry_after(self) -> float:
        """
        Get seconds until next token is available.

        Returns:
            Seconds to wait before retry (0 if tokens available).
        """
        with self.lock:
            self._refill()
            if self.tokens >= 1:
                return 0.0

            # Calculate time needed to refill 1 token
            return 1.0 / self.refill_rate


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """
    Singleton rate limiter for MCP tools.

    Manages per-tool and global rate limits using token buckets.
    Configurable via environment variables and settings.local.json.
    """

    _instance: Optional['RateLimiter'] = None
    _lock = threading.Lock()

    def __init__(
        self,
        tool_limits: Optional[Dict[str, RateLimitConfig]] = None,
        global_limit: Optional[RateLimitConfig] = None,
        enabled: bool = True
    ):
        """
        Initialize rate limiter.

        Args:
            tool_limits: Per-tool rate limit configurations.
            global_limit: Global rate limit configuration.
            enabled: Whether rate limiting is enabled.
        """
        self.enabled = enabled
        self.tool_limits = tool_limits or DEFAULT_TOOL_LIMITS.copy()
        self.global_limit = global_limit or DEFAULT_GLOBAL_LIMIT

        # Create token buckets
        self.tool_buckets: Dict[str, TokenBucket] = {}
        for tool_name, config in self.tool_limits.items():
            self.tool_buckets[tool_name] = TokenBucket(config)

        self.global_bucket = TokenBucket(self.global_limit)

        # Metrics integration
        self._init_metrics()

        logger.info(
            f"Rate limiter initialized: enabled={enabled}, "
            f"global_limit={global_limit.requests_per_minute} RPM, "
            f"tools_configured={len(self.tool_limits)}"
        )

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics for rate limiting."""
        try:
            from mcp.metrics import RATE_LIMIT_HITS, RATE_LIMIT_TOKENS

            self.rate_limit_hits = RATE_LIMIT_HITS
            self.rate_limit_tokens = RATE_LIMIT_TOKENS
            self.metrics_available = True
        except ImportError:
            self.metrics_available = False

    @classmethod
    def get_instance(cls) -> 'RateLimiter':
        """
        Get singleton instance of rate limiter.

        Returns:
            RateLimiter instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Load configuration
                    enabled = os.environ.get(
                        "EROS_RATE_LIMIT_ENABLED",
                        "true"
                    ).lower() == "true"

                    # Load custom limits from settings if available
                    tool_limits, global_limit = cls._load_config()

                    cls._instance = cls(
                        tool_limits=tool_limits,
                        global_limit=global_limit,
                        enabled=enabled
                    )

        return cls._instance

    @classmethod
    def _load_config(cls) -> tuple[Dict[str, RateLimitConfig], RateLimitConfig]:
        """
        Load rate limit configuration from settings.local.json.

        Returns:
            Tuple of (tool_limits, global_limit).
        """
        tool_limits = DEFAULT_TOOL_LIMITS.copy()
        global_limit = DEFAULT_GLOBAL_LIMIT

        # Try to load from settings.local.json
        settings_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "settings.local.json"
        )

        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)

                # Check for rate_limiting section
                if "rate_limiting" in settings:
                    rl_config = settings["rate_limiting"]

                    # Load global limit
                    if "global" in rl_config:
                        global_cfg = rl_config["global"]
                        global_limit = RateLimitConfig(
                            global_cfg.get("requests_per_minute", 500),
                            global_cfg.get("burst_capacity", 600)
                        )

                    # Load tool-specific limits
                    if "tools" in rl_config:
                        for tool_name, cfg in rl_config["tools"].items():
                            tool_limits[tool_name] = RateLimitConfig(
                                cfg.get("requests_per_minute", 30),
                                cfg.get("burst_capacity", cfg.get("requests_per_minute", 30))
                            )

                    logger.info(f"Loaded rate limiting config from {settings_path}")
            except Exception as e:
                logger.warning(f"Failed to load rate limiting config: {e}")

        return tool_limits, global_limit

    def consume(self, tool_name: str, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens for a tool request.

        Checks both per-tool and global rate limits.

        Args:
            tool_name: Name of the tool being called.
            tokens: Number of tokens to consume (default: 1).

        Returns:
            True if request is allowed, False if rate limited.
        """
        if not self.enabled:
            return True

        # Check global limit first (cheaper check)
        if not self.global_bucket.consume(tokens):
            if self.metrics_available:
                self.rate_limit_hits.labels(
                    tool=tool_name,
                    limit_type='global'
                ).inc()
            logger.warning(f"Global rate limit exceeded for tool: {tool_name}")
            return False

        # Check per-tool limit
        tool_bucket = self._get_or_create_bucket(tool_name)
        if not tool_bucket.consume(tokens):
            # Return token to global bucket since we're rejecting
            self.global_bucket.tokens = min(
                self.global_bucket.capacity,
                self.global_bucket.tokens + tokens
            )

            if self.metrics_available:
                self.rate_limit_hits.labels(
                    tool=tool_name,
                    limit_type='tool'
                ).inc()
            logger.warning(f"Tool rate limit exceeded: {tool_name}")
            return False

        # Update metrics
        if self.metrics_available:
            self.rate_limit_tokens.labels(tool=tool_name).set(
                tool_bucket.get_available_tokens()
            )

        return True

    def _get_or_create_bucket(self, tool_name: str) -> TokenBucket:
        """
        Get or create token bucket for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            TokenBucket for the tool.
        """
        if tool_name not in self.tool_buckets:
            # Use default limit for unconfigured tools
            config = self.tool_limits.get(tool_name, DEFAULT_TOOL_LIMIT)
            self.tool_buckets[tool_name] = TokenBucket(config)

        return self.tool_buckets[tool_name]

    def get_retry_after(self, tool_name: str) -> float:
        """
        Get seconds until retry is allowed for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Seconds to wait before retry.
        """
        if not self.enabled:
            return 0.0

        # Return max of global and tool-specific retry delay
        global_retry = self.global_bucket.get_retry_after()

        tool_bucket = self._get_or_create_bucket(tool_name)
        tool_retry = tool_bucket.get_retry_after()

        return max(global_retry, tool_retry)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with rate limiter stats.
        """
        stats = {
            "enabled": self.enabled,
            "global": {
                "requests_per_minute": int(self.global_limit.requests_per_minute),
                "burst_capacity": self.global_limit.burst_capacity,
                "available_tokens": self.global_bucket.get_available_tokens(),
                "retry_after": self.global_bucket.get_retry_after(),
            },
            "tools": {}
        }

        for tool_name, bucket in self.tool_buckets.items():
            config = self.tool_limits.get(tool_name, DEFAULT_TOOL_LIMIT)
            stats["tools"][tool_name] = {
                "requests_per_minute": int(config.requests_per_minute),
                "burst_capacity": config.burst_capacity,
                "available_tokens": bucket.get_available_tokens(),
                "retry_after": bucket.get_retry_after(),
            }

        return stats


# =============================================================================
# Rate Limit Exception
# =============================================================================

class RateLimitExceeded(Exception):
    """
    Exception raised when rate limit is exceeded.

    Attributes:
        tool_name: Name of the rate-limited tool.
        retry_after: Seconds until retry is allowed.
        limit_type: Type of limit exceeded ('tool' or 'global').
    """

    def __init__(
        self,
        tool_name: str,
        retry_after: float,
        limit_type: str = "tool"
    ):
        """
        Initialize rate limit exception.

        Args:
            tool_name: Name of the rate-limited tool.
            retry_after: Seconds until retry is allowed.
            limit_type: Type of limit exceeded ('tool' or 'global').
        """
        self.tool_name = tool_name
        self.retry_after = retry_after
        self.limit_type = limit_type

        super().__init__(
            f"Rate limit exceeded for {tool_name} ({limit_type}). "
            f"Retry after {retry_after:.2f} seconds."
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary format for MCP error response.

        Returns:
            Dictionary representation of the error.
        """
        return {
            "error": "RateLimitExceeded",
            "message": str(self),
            "tool": self.tool_name,
            "retry_after": round(self.retry_after, 2),
            "limit_type": self.limit_type,
            "http_status_equivalent": 429
        }


# =============================================================================
# Helper Functions
# =============================================================================

def check_rate_limit(tool_name: str, tokens: int = 1) -> None:
    """
    Check rate limit for a tool and raise exception if exceeded.

    Args:
        tool_name: Name of the tool being called.
        tokens: Number of tokens to consume (default: 1).

    Raises:
        RateLimitExceeded: If rate limit is exceeded.
    """
    limiter = RateLimiter.get_instance()

    if not limiter.consume(tool_name, tokens):
        retry_after = limiter.get_retry_after(tool_name)

        # Determine limit type
        tool_bucket = limiter._get_or_create_bucket(tool_name)
        global_retry = limiter.global_bucket.get_retry_after()
        tool_retry = tool_bucket.get_retry_after()

        limit_type = "global" if global_retry >= tool_retry else "tool"

        raise RateLimitExceeded(tool_name, retry_after, limit_type)


def get_rate_limit_stats() -> Dict[str, Any]:
    """
    Get current rate limiter statistics.

    Returns:
        Dictionary with rate limiter stats.
    """
    limiter = RateLimiter.get_instance()
    return limiter.get_stats()


def reset_rate_limiter() -> None:
    """
    Reset the singleton rate limiter instance.

    Useful for testing or reloading configuration.
    """
    with RateLimiter._lock:
        RateLimiter._instance = None
    logger.info("Rate limiter instance reset")
