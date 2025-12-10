"""
Agent Invoker for EROS Schedule Generator.

This module provides utilities for invoking specialized sub-agents during
schedule generation. It handles agent discovery, invocation, caching,
timeout management, and fallback behavior.

Designed for use with Claude Code's native agent system.

Content Type Awareness (v2.1):
    - Supports 20+ schedulable content types across 4 tiers
    - Content type filtering by page type (paid/free/both)
    - Priority-based distribution and rotation patterns
    - Fallback strategies for all agents

Supported Content Types:
    Tier 1 - Direct Revenue: ppv, ppv_follow_up, bundle, flash_bundle, snapchat_bundle
    Tier 2 - Feed/Wall: vip_post, first_to_tip, link_drop, normal_post_bump, renew_on_post,
                        game_post, flyer_gif_bump, descriptive_bump, wall_link_drop, live_promo
    Tier 3 - Engagement: dm_farm, like_farm, text_only_bump
    Tier 4 - Retention: renew_on_mm, expired_subscriber
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from shared_context import (
    AgentInvokerMode,
    AgentRequest,
    AgentResponse,
    FollowUpSequence,
    PageTypeRules,
    PricingStrategy,
    RevenueProjection,
    RotationStrategy,
    ScheduleContext,
    TimingStrategy,
    ValidationResult,
)

if TYPE_CHECKING:
    from content_type_registry import ContentTypeRegistry, SchedulableContentType


@dataclass
class AgentConfig:
    """Configuration for a sub-agent."""

    name: str
    model: str  # haiku, sonnet, opus
    timeout_seconds: int
    cache_duration_days: int
    tools: list[str]


@dataclass
class AgentMetrics:
    """
    Track agent invocation metrics for observability and optimization.

    Provides visibility into:
    - Total invocation counts per agent
    - Fallback rates (indicates agent reliability)
    - Timing data for performance monitoring
    - Cache hit rates (indicates cache efficiency)
    """

    invocations: dict[str, int] = field(default_factory=dict)
    fallback_count: dict[str, int] = field(default_factory=dict)
    total_time_ms: dict[str, float] = field(default_factory=dict)
    cache_hits: dict[str, int] = field(default_factory=dict)
    errors: dict[str, list[str]] = field(default_factory=dict)

    def record_invocation(
        self,
        agent_name: str,
        success: bool,
        time_ms: float,
        cached: bool = False,
        error_msg: str | None = None,
    ) -> None:
        """
        Record a single agent invocation.

        Args:
            agent_name: Name of the agent invoked
            success: Whether the invocation succeeded (False = fallback used)
            time_ms: Execution time in milliseconds
            cached: Whether result came from cache
            error_msg: Optional error message if invocation failed
        """
        self.invocations[agent_name] = self.invocations.get(agent_name, 0) + 1
        self.total_time_ms[agent_name] = self.total_time_ms.get(agent_name, 0) + time_ms

        if not success:
            self.fallback_count[agent_name] = self.fallback_count.get(agent_name, 0) + 1

        if cached:
            self.cache_hits[agent_name] = self.cache_hits.get(agent_name, 0) + 1

        if error_msg:
            if agent_name not in self.errors:
                self.errors[agent_name] = []
            # Keep only last 10 errors per agent
            self.errors[agent_name] = (self.errors[agent_name] + [error_msg])[-10:]

    def get_fallback_rate(self, agent_name: str) -> float:
        """Get fallback rate for a specific agent (0.0 to 1.0)."""
        total = self.invocations.get(agent_name, 0)
        fallbacks = self.fallback_count.get(agent_name, 0)
        return fallbacks / total if total > 0 else 0.0

    def get_cache_hit_rate(self, agent_name: str) -> float:
        """Get cache hit rate for a specific agent (0.0 to 1.0)."""
        total = self.invocations.get(agent_name, 0)
        hits = self.cache_hits.get(agent_name, 0)
        return hits / total if total > 0 else 0.0

    def get_avg_time_ms(self, agent_name: str) -> float:
        """Get average execution time in milliseconds for an agent."""
        total = self.invocations.get(agent_name, 0)
        time_sum = self.total_time_ms.get(agent_name, 0)
        return time_sum / total if total > 0 else 0.0

    def get_summary(self) -> dict[str, Any]:
        """
        Get a comprehensive summary of all metrics.

        Returns:
            Dict with aggregated stats and per-agent breakdown
        """
        total_invocations = sum(self.invocations.values())
        total_fallbacks = sum(self.fallback_count.values())
        total_cache_hits = sum(self.cache_hits.values())

        return {
            "total_invocations": total_invocations,
            "total_fallbacks": total_fallbacks,
            "total_cache_hits": total_cache_hits,
            "overall_fallback_rate": total_fallbacks / total_invocations
            if total_invocations > 0
            else 0.0,
            "overall_cache_hit_rate": total_cache_hits / total_invocations
            if total_invocations > 0
            else 0.0,
            "agents": {
                name: {
                    "invocations": self.invocations.get(name, 0),
                    "fallback_rate": self.get_fallback_rate(name),
                    "cache_hit_rate": self.get_cache_hit_rate(name),
                    "avg_time_ms": round(self.get_avg_time_ms(name), 2),
                    "recent_errors": self.errors.get(name, [])[-3:],
                }
                for name in self.invocations
            },
        }

    def reset(self) -> None:
        """Reset all metrics (useful for testing or new sessions)."""
        self.invocations.clear()
        self.fallback_count.clear()
        self.total_time_ms.clear()
        self.cache_hits.clear()
        self.errors.clear()


# Agent configurations - v2.0 consolidated agents
# Maps to agent files in ~/.claude/agents/eros-scheduling/
AGENT_CONFIGS: dict[str, AgentConfig] = {
    # Phase 1: Data Collection (fast, parallel)
    "timezone-optimizer": AgentConfig(
        name="timezone-optimizer",
        model="haiku",
        timeout_seconds=15,
        cache_duration_days=30,
        tools=["Read", "Bash"],
    ),
    "onlyfans-business-analyst": AgentConfig(
        name="onlyfans-business-analyst",
        model="opus",
        timeout_seconds=45,
        cache_duration_days=14,
        tools=["Read", "Bash", "WebFetch"],
    ),
    # Phase 2: Optimization (sequential, context-dependent)
    "content-strategy-optimizer": AgentConfig(
        name="content-strategy-optimizer",
        model="sonnet",
        timeout_seconds=30,
        cache_duration_days=7,
        tools=["Read", "Bash"],
    ),
    "volume-calibrator": AgentConfig(
        name="volume-calibrator",
        model="haiku",  # Changed from sonnet - rule-based calculation
        timeout_seconds=30,
        cache_duration_days=3,
        tools=["Read", "Bash"],
    ),
    "revenue-optimizer": AgentConfig(
        name="revenue-optimizer",
        model="sonnet",
        timeout_seconds=30,
        cache_duration_days=7,
        tools=["Read", "Bash"],
    ),
    # Phase 3: Follow-up Design
    "multi-touch-sequencer": AgentConfig(
        name="multi-touch-sequencer",
        model="opus",
        timeout_seconds=45,
        cache_duration_days=1,
        tools=["Read", "Bash"],
    ),
    # Phase 4: Validation (never cached)
    "validation-guardian": AgentConfig(
        name="validation-guardian",
        model="sonnet",
        timeout_seconds=30,
        cache_duration_days=0,  # Never cache validation
        tools=["Read", "Bash"],
    ),
}

# Legacy agent name mappings for backward compatibility
# Maps old deprecated agent names to new consolidated agents
AGENT_NAME_MAPPINGS: dict[str, str] = {
    "pricing-strategist": "revenue-optimizer",
    "page-type-optimizer": "volume-calibrator",
    "content-rotation-architect": "content-strategy-optimizer",
    "revenue-forecaster": "revenue-optimizer",
}

# Agent directory path
AGENTS_DIR = Path.home() / ".claude" / "agents" / "eros-scheduling"

# Cache directory
CACHE_DIR = Path.home() / ".eros" / "agent_cache"


class AgentInvoker:
    """
    Manages invocation of specialized sub-agents for schedule generation.

    This class handles:
    - Agent discovery and availability checking
    - Cache management for agent outputs
    - Fallback behavior when agents are unavailable
    - Result parsing and validation
    - Hybrid mode: output requests for Claude to invoke, then resume
    """

    def __init__(
        self,
        db_path: str | None = None,
        mode: AgentInvokerMode = AgentInvokerMode.FALLBACK_ONLY,
    ):
        """Initialize the invoker with optional database path and mode."""
        self.db_path = db_path or self._find_database()
        self.mode = mode
        self._cache: dict[str, Any] = {}
        self._ensure_cache_dir()

        # Hybrid mode state
        self.pending_requests: list[AgentRequest] = []
        self.received_responses: dict[str, AgentResponse] = {}

        # Instrumentation metrics
        self.metrics = AgentMetrics()

    def _find_database(self) -> str:
        """Find the EROS database path with proper env var priority."""
        # Priority 1: Environment variable
        env_path = os.environ.get("EROS_DATABASE_PATH", "")
        if env_path:
            env_db = Path(env_path)
            if env_db.exists():
                return str(env_db)
            # Warn but continue to fallbacks
            print(
                f"  [WARNING] EROS_DATABASE_PATH={env_path} not found, trying fallbacks",
                file=sys.stderr,
            )

        # Priority 2-4: Standard locations
        fallback_paths = [
            Path.home() / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
            Path.home() / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
            Path.home() / ".eros" / "eros.db",
        ]

        for path in fallback_paths:
            if path.exists():
                return str(path)

        raise FileNotFoundError(
            "EROS database not found. Set EROS_DATABASE_PATH or place database at ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
        )

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, agent_name: str, context: dict[str, Any]) -> str:
        """
        Generate a cache key for an agent invocation.

        Includes all variant factors that affect output:
        - creator_id: Different creators get different strategies
        - week: Time-sensitive optimizations
        - page_type: Paid vs free page rules differ
        - volume_level: Affects capacity and distribution
        - content_types: Different type sets produce different strategies
        """
        # Extract variant factors with safe defaults
        cache_context = {
            "creator_id": context.get("creator_id"),
            "week": str(context.get("week_start") or context.get("week", "")),
            "page_type": context.get("page_type"),
            "volume_level": context.get("volume_level"),
            "content_types": sorted(context.get("enabled_content_types", []))
            if context.get("enabled_content_types")
            else None,
        }
        # Remove None values to keep cache keys clean
        cache_context = {k: v for k, v in cache_context.items() if v is not None}
        context_str = json.dumps(cache_context, sort_keys=True, default=str)
        hash_input = f"{agent_name}:{context_str}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _get_cached_result(self, agent_name: str, cache_key: str) -> dict[str, Any] | None:
        """Check if a cached result exists and is valid."""
        config = AGENT_CONFIGS.get(agent_name)
        if not config or config.cache_duration_days == 0:
            return None

        cache_file = CACHE_DIR / f"{agent_name}_{cache_key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)

            cached_at = datetime.fromisoformat(cached.get("cached_at", ""))
            expires_at = cached_at + timedelta(days=config.cache_duration_days)

            if datetime.now() < expires_at:
                return cached.get("result")
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return None

    def _save_to_cache(self, agent_name: str, cache_key: str, result: dict[str, Any]) -> None:
        """Save a result to the cache."""
        config = AGENT_CONFIGS.get(agent_name)
        if not config or config.cache_duration_days == 0:
            return

        cache_file = CACHE_DIR / f"{agent_name}_{cache_key}.json"
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "agent": agent_name,
            "result": result,
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2, default=str)

    def _resolve_agent_name(self, agent_name: str) -> str:
        """Resolve legacy agent names to v2.0 consolidated agent names."""
        return AGENT_NAME_MAPPINGS.get(agent_name, agent_name)

    def _build_agent_context(
        self, context: ScheduleContext, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Build standardized context dict for agent invocation.

        This ensures all agents receive a consistent context structure,
        which is critical for:
        - Accurate cache key generation
        - Reproducible agent behavior
        - Debugging and logging

        Args:
            context: The ScheduleContext containing schedule generation state
            extra: Optional additional context fields to merge

        Returns:
            Dict with standardized keys for agent consumption
        """
        # Extract volume_level from creator_profile if available
        volume_level = None
        page_type = None
        if context.creator_profile:
            volume_level = getattr(context.creator_profile, "volume_level", None)
            page_type = getattr(context.creator_profile, "page_type", None)

        # Extract enabled_content_types if available (may not exist on all contexts)
        enabled_content_types = getattr(context, "enabled_content_types", None)

        base: dict[str, Any] = {
            "creator_id": context.creator_id,
            "page_type": page_type,
            "volume_level": volume_level,
            "week_start": str(context.week_start) if context.week_start else None,
            "week_end": str(context.week_end) if context.week_end else None,
            "mode": context.mode,
            "enabled_content_types": list(enabled_content_types) if enabled_content_types else [],
            "database_path": self.db_path,
        }

        # Add creator profile details if available
        if context.creator_profile:
            base["creator_profile"] = {
                "page_name": getattr(context.creator_profile, "page_name", None),
                "display_name": getattr(context.creator_profile, "display_name", None),
                "page_type": page_type,
                "subscription_price": getattr(context.creator_profile, "subscription_price", None),
                "current_active_fans": getattr(context.creator_profile, "current_active_fans", None),
                "performance_tier": getattr(context.creator_profile, "performance_tier", None),
                "volume_level": volume_level,
            }

        # Add persona profile if available
        if context.persona_profile:
            base["persona_profile"] = {
                "primary_tone": getattr(context.persona_profile, "primary_tone", None),
                "emoji_frequency": getattr(context.persona_profile, "emoji_frequency", None),
                "slang_level": getattr(context.persona_profile, "slang_level", None),
            }

        # Merge extra context (overwrites base keys if present)
        if extra:
            base.update(extra)

        return base

    def is_agent_available(self, agent_name: str) -> bool:
        """Check if an agent file exists (resolves legacy names)."""
        resolved_name = self._resolve_agent_name(agent_name)
        agent_file = AGENTS_DIR / f"{resolved_name}.md"
        return agent_file.exists()

    def get_available_agents(self) -> list[str]:
        """Get list of available agents."""
        if not AGENTS_DIR.exists():
            return []
        return [f.stem for f in AGENTS_DIR.glob("*.md")]

    def get_metrics_summary(self) -> dict[str, Any]:
        """
        Get a summary of agent invocation metrics.

        Returns comprehensive stats useful for:
        - Monitoring agent health and performance
        - Identifying agents with high fallback rates
        - Optimizing cache strategies
        - Debugging invocation issues

        Returns:
            Dict with total counts, per-agent breakdowns, and rates
        """
        return self.metrics.get_summary()

    def reset_metrics(self) -> None:
        """Reset all metrics (useful between sessions or for testing)."""
        self.metrics.reset()

    # ========================================================================
    # HYBRID MODE METHODS
    # ========================================================================

    def output_agent_request(self, request: AgentRequest) -> None:
        """
        Output an agent request for Claude to process.

        In hybrid mode, this outputs a structured JSON block that Claude
        can detect and use to invoke the Task tool with the appropriate agent.
        """
        output = {
            "type": "AGENT_REQUEST",
            "request_id": request.request_id,
            "agent_name": request.agent_name,
            "agent_model": request.agent_model,
            "timeout_seconds": request.timeout_seconds,
            "context": request.context,
            "expected_output": request.expected_output_schema,
            "cache_key": request.cache_key,
        }
        # Use markers that Claude can easily detect
        print("<<<AGENT_REQUEST>>>", file=sys.stderr)
        print(json.dumps(output, indent=2, default=str), file=sys.stderr)
        print("<<<END_AGENT_REQUEST>>>", file=sys.stderr)
        sys.stderr.flush()

    def load_agent_responses(self, responses_file: str) -> int:
        """
        Load agent responses from a JSON file (written by Claude orchestration).

        Returns the number of responses loaded.
        """
        path = Path(responses_file)
        if not path.exists():
            return 0

        try:
            with open(path) as f:
                data = json.load(f)

            responses = data.get("responses", [])
            for resp_data in responses:
                response = AgentResponse(
                    request_id=resp_data.get("request_id", ""),
                    agent_name=resp_data.get("agent_name", ""),
                    success=resp_data.get("success", False),
                    result=resp_data.get("result"),
                    error=resp_data.get("error"),
                    fallback_used=resp_data.get("fallback_used", False),
                    execution_time_ms=resp_data.get("execution_time_ms", 0),
                    cached=resp_data.get("cached", False),
                )
                self.received_responses[response.request_id] = response

            return len(responses)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [ERROR] Failed to load agent responses: {e}", file=sys.stderr)
            return 0

    def has_pending_requests(self) -> bool:
        """Check if there are unresolved agent requests."""
        # A request is unresolved if we haven't received a response for it
        for request in self.pending_requests:
            if request.request_id not in self.received_responses:
                return True
        return False

    def get_pending_request_ids(self) -> list[str]:
        """Get list of pending (unresolved) request IDs."""
        return [
            r.request_id
            for r in self.pending_requests
            if r.request_id not in self.received_responses
        ]

    def get_response(self, request_id: str) -> AgentResponse | None:
        """Get a received response by request ID."""
        return self.received_responses.get(request_id)

    def create_agent_request(
        self,
        agent_name: str,
        context: ScheduleContext,
        extra_context: dict[str, Any] | None = None,
    ) -> AgentRequest:
        """Create an AgentRequest for the specified agent."""
        resolved_name = self._resolve_agent_name(agent_name)
        config = AGENT_CONFIGS.get(resolved_name)

        if not config:
            raise ValueError(f"Unknown agent: {resolved_name}")

        # Build context dict
        ctx = {
            "creator_id": context.creator_id,
            "week_start": str(context.week_start) if context.week_start else None,
            "week_end": str(context.week_end) if context.week_end else None,
            "mode": context.mode,
            "database_path": self.db_path,
        }

        # Add creator profile if available
        if context.creator_profile:
            ctx["creator_profile"] = {
                "page_name": context.creator_profile.page_name,
                "display_name": context.creator_profile.display_name,
                "page_type": context.creator_profile.page_type,
                "subscription_price": context.creator_profile.subscription_price,
                "current_active_fans": context.creator_profile.current_active_fans,
                "performance_tier": context.creator_profile.performance_tier,
                "volume_level": context.creator_profile.volume_level,
            }

        # Add persona profile if available
        if context.persona_profile:
            ctx["persona_profile"] = {
                "primary_tone": context.persona_profile.primary_tone,
                "emoji_frequency": context.persona_profile.emoji_frequency,
                "slang_level": context.persona_profile.slang_level,
            }

        # Merge extra context
        if extra_context:
            ctx.update(extra_context)

        # Generate cache key
        cache_context = {"creator_id": context.creator_id, "week": str(context.week_start)}
        cache_key = self._get_cache_key(resolved_name, cache_context)

        return AgentRequest(
            request_id=f"req_{resolved_name}_{uuid.uuid4().hex[:8]}",
            agent_name=resolved_name,
            agent_model=config.model,
            timeout_seconds=config.timeout_seconds,
            context=ctx,
            expected_output_schema=self._get_expected_schema(resolved_name),
            cache_key=cache_key if config.cache_duration_days > 0 else None,
        )

    def _get_expected_schema(self, agent_name: str) -> str:
        """Get the expected output schema name for an agent."""
        schema_map = {
            "timezone-optimizer": "TimingStrategy",
            "volume-calibrator": "PageTypeRules",
            "content-strategy-optimizer": "RotationStrategy",
            "revenue-optimizer": "PricingStrategy",
            "multi-touch-sequencer": "FollowUpSequence",
            "validation-guardian": "ValidationResult",
            "onlyfans-business-analyst": "BusinessAnalysis",
        }
        return schema_map.get(agent_name, "dict")

    # ========================================================================
    # ERROR RECOVERY METHODS
    # ========================================================================

    def _invoke_with_retry(
        self,
        agent_name: str,
        invoke_fn: Callable[[ScheduleContext], tuple[Any, bool]],
        fallback_fn: Callable[[ScheduleContext], Any],
        context: ScheduleContext,
        max_retries: int = 2,
    ) -> tuple[Any, bool]:
        """
        Invoke an agent with retry logic, fallback chain, and metrics tracking.

        This is the central invocation method that provides:
        - Automatic retry on transient failures
        - Output validation before accepting results
        - Fallback execution when retries exhausted
        - Comprehensive metrics tracking

        Args:
            agent_name: Name of the agent being invoked
            invoke_fn: Function to invoke (should return (result, fallback_used))
            fallback_fn: Function to get fallback value (should return result)
            context: Schedule context
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (result, fallback_used)
        """
        start_time = time.time()
        last_error: Exception | None = None
        last_error_msg: str | None = None

        for attempt in range(max_retries):
            try:
                result, fallback_used = invoke_fn(context)

                # Validate the result has expected structure
                if result is not None and not fallback_used:
                    if self._validate_agent_output(agent_name, result):
                        # Success - record metrics
                        elapsed_ms = (time.time() - start_time) * 1000
                        self.metrics.record_invocation(
                            agent_name=agent_name,
                            success=True,
                            time_ms=elapsed_ms,
                            cached=False,
                        )
                        return result, False
                    print(
                        f"  [AGENT] {agent_name} output validation failed, retrying...",
                        file=sys.stderr,
                    )
                    last_error_msg = "Output validation failed"
                else:
                    # Fallback was used in invoke_fn
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.metrics.record_invocation(
                        agent_name=agent_name,
                        success=not fallback_used,
                        time_ms=elapsed_ms,
                        cached=False,
                    )
                    return result, fallback_used

            except Exception as e:
                last_error = e
                last_error_msg = str(e)
                print(
                    f"  [AGENT] {agent_name} attempt {attempt + 1}/{max_retries} failed: {e}",
                    file=sys.stderr,
                )

        # All retries exhausted - use fallback
        elapsed_ms = (time.time() - start_time) * 1000
        if last_error:
            print(
                f"  [AGENT] {agent_name} failed after {max_retries} attempts, using fallback",
                file=sys.stderr,
            )

        # Record fallback usage in metrics
        self.metrics.record_invocation(
            agent_name=agent_name,
            success=False,
            time_ms=elapsed_ms,
            cached=False,
            error_msg=last_error_msg,
        )

        context.mark_fallback_used(agent_name)
        return fallback_fn(context), True

    def _invoke_with_cache_and_metrics(
        self,
        agent_name: str,
        context: ScheduleContext,
        cache_context: dict[str, Any],
        use_cache: bool,
        result_class: type,
        fallback_fn: Callable[[ScheduleContext], Any],
        extra_context: dict[str, Any] | None = None,
    ) -> tuple[Any, bool]:
        """
        Unified invocation method with caching, metrics, and standardized context.

        This method consolidates the common logic from all invoke_* methods:
        1. Check cache (if enabled)
        2. Check agent availability
        3. Handle hybrid mode
        4. Track metrics
        5. Return result or fallback

        Args:
            agent_name: Name of the agent (already resolved)
            context: Schedule context
            cache_context: Context dict for cache key generation
            use_cache: Whether to use caching
            result_class: Class to instantiate from cached/response dict
            fallback_fn: Function to call for fallback
            extra_context: Additional context for agent request

        Returns:
            Tuple of (result, fallback_used)
        """
        start_time = time.time()

        # Build full context with variant factors for cache key
        full_cache_context = self._build_agent_context(context, cache_context)
        cache_key = self._get_cache_key(agent_name, full_cache_context)

        # Check cache first
        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.record_invocation(
                    agent_name=agent_name,
                    success=True,
                    time_ms=elapsed_ms,
                    cached=True,
                )
                return result_class(**cached), False

        # Check if agent is available
        if not self.is_agent_available(agent_name):
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                cached=False,
                error_msg="Agent not available",
            )
            context.mark_fallback_used(agent_name)
            return fallback_fn(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            # Check if we already have a response (resume mode)
            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.metrics.record_invocation(
                        agent_name=agent_name,
                        success=True,
                        time_ms=elapsed_ms,
                        cached=False,
                    )
                    context.mark_agent_used(agent_name)
                    return result_class(**response.result), False

            # Output request for Claude and return fallback for now
            self.output_agent_request(request)
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                cached=False,
                error_msg="Hybrid mode - awaiting Claude response",
            )
            return fallback_fn(context), True

        # FALLBACK_ONLY MODE: Use fallback (but mark as "used" for tracking)
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.record_invocation(
            agent_name=agent_name,
            success=False,
            time_ms=elapsed_ms,
            cached=False,
            error_msg="Fallback-only mode",
        )
        context.mark_agent_used(agent_name)
        return fallback_fn(context), True

    def _validate_agent_output(self, agent_name: str, result: Any) -> bool:
        """
        Validate that an agent's output has the expected structure.

        Returns True if valid, False otherwise.
        """
        if result is None:
            return False

        # Basic type checks based on agent
        try:
            if agent_name == "timezone-optimizer":
                return hasattr(result, "peak_windows") and hasattr(result, "timezone")
            elif agent_name == "volume-calibrator":
                return hasattr(result, "rules_applied") and hasattr(result, "page_type")
            elif agent_name == "revenue-optimizer":
                return hasattr(result, "content_type_prices") or hasattr(result, "projections")
            elif agent_name == "content-strategy-optimizer":
                return hasattr(result, "weekly_rotation")
            elif agent_name == "multi-touch-sequencer":
                return hasattr(result, "sequence")
            elif agent_name == "validation-guardian":
                return hasattr(result, "validation_passed")
            else:
                return True  # Unknown agent, assume valid
        except Exception:
            return False

    # ========================================================================
    # FALLBACK METHODS
    # ========================================================================

    def get_fallback_pricing(self, context: ScheduleContext) -> PricingStrategy:
        """
        Generate fallback pricing when agent unavailable.

        Context-aware enhancements:
        - Uses page_type to apply conservative pricing for free pages (10-15% lower)
        - Applies payday_multipliers from context if available
        - Uses performance_tier to adjust base prices
        """
        profile = context.creator_profile
        is_paid = profile.page_type == "paid" if profile else True

        # Base prices - apply 10-15% reduction for free pages (conservative approach)
        free_page_discount = 0.85  # 15% lower for free pages
        base_prices = {
            "solo": 15.0 if is_paid else 15.0 * free_page_discount,
            "bundle": 25.0 if is_paid else 25.0 * free_page_discount,
            "sextape": 30.0 if is_paid else 30.0 * free_page_discount,
            "bg": 35.0 if is_paid else 35.0 * free_page_discount,
            "winner": 20.0 if is_paid else 20.0 * free_page_discount,
            "custom": 40.0 if is_paid else 40.0 * free_page_discount,
        }

        # Adjust based on performance tier (if available)
        tier_adjustment = 1.0
        if profile:
            tier = profile.performance_tier
            if tier == 1:
                # Tier 1 creators can command premium prices
                tier_adjustment = 1.10
            elif tier == 3:
                # Tier 3 creators should use more competitive pricing
                tier_adjustment = 0.90

        # Apply tier adjustment
        for ct in base_prices:
            base_prices[ct] = round(base_prices[ct] * tier_adjustment, 2)

        # Build content type prices with reasoning
        reasoning = "Default tier pricing"
        if not is_paid:
            reasoning += " (free page discount applied)"
        if tier_adjustment != 1.0:
            reasoning += f" (tier {profile.performance_tier if profile else 2} adjustment)"

        return PricingStrategy(
            content_type_prices={
                ct: {"base": price, "optimized": price, "reasoning": reasoning}
                for ct, price in base_prices.items()
            },
            page_type_modifier=1.0 if is_paid else free_page_discount,
            weekly_revenue_projection=0.0,
            generated_at=datetime.now().isoformat(),
        )

    def get_fallback_timing(self, context: ScheduleContext) -> TimingStrategy:
        """
        Generate fallback timing when agent unavailable.

        Context-aware enhancements:
        - If context.timing is partially populated (e.g., from cached data), use those values
        - Sets fallback_hours_used flag on context
        - Uses 0.7 confidence instead of static defaults when partial data available
        """
        # Mark that we're using fallback hours
        context.fallback_hours_used = True

        # Check if we have partial timing data in context to use
        if context.timing is not None:
            # We have some timing data - use it with reduced confidence
            context.best_hours_confidence = 0.7  # Partial data confidence
            existing = context.timing

            # Use existing data where available, fill gaps with defaults
            return TimingStrategy(
                timezone=existing.timezone or "America/New_York",
                peak_windows=existing.peak_windows
                if existing.peak_windows
                else [
                    {"start": "18:00", "end": "22:00", "tier": 1, "expected_lift": 1.35},
                    {"start": "10:00", "end": "12:00", "tier": 2, "expected_lift": 1.15},
                ],
                avoid_windows=existing.avoid_windows
                if existing.avoid_windows
                else [{"start": "03:00", "end": "06:00", "reason": "lowest_engagement"}],
                best_days=existing.best_days
                if existing.best_days
                else ["Sunday", "Friday", "Saturday"],
                daily_schedule=existing.daily_schedule
                if existing.daily_schedule
                else {
                    "Monday": ["10:00", "18:00", "21:00"],
                    "Tuesday": ["10:00", "14:00", "19:00", "22:00"],
                    "Wednesday": ["10:00", "18:00", "21:00"],
                    "Thursday": ["10:00", "14:00", "19:00", "22:00"],
                    "Friday": ["10:00", "18:00", "21:00", "23:00"],
                    "Saturday": ["12:00", "18:00", "21:00", "23:00"],
                    "Sunday": ["12:00", "18:00", "21:00"],
                },
                generated_at=datetime.now().isoformat(),
            )

        # No existing data - use static defaults with low confidence
        context.best_hours_confidence = 0.5  # Static default confidence

        return TimingStrategy(
            timezone="America/New_York",
            peak_windows=[
                {"start": "18:00", "end": "22:00", "tier": 1, "expected_lift": 1.35},
                {"start": "10:00", "end": "12:00", "tier": 2, "expected_lift": 1.15},
            ],
            avoid_windows=[{"start": "03:00", "end": "06:00", "reason": "lowest_engagement"}],
            best_days=["Sunday", "Friday", "Saturday"],
            daily_schedule={
                "Monday": ["10:00", "18:00", "21:00"],
                "Tuesday": ["10:00", "14:00", "19:00", "22:00"],
                "Wednesday": ["10:00", "18:00", "21:00"],
                "Thursday": ["10:00", "14:00", "19:00", "22:00"],
                "Friday": ["10:00", "18:00", "21:00", "23:00"],
                "Saturday": ["12:00", "18:00", "21:00", "23:00"],
                "Sunday": ["12:00", "18:00", "21:00"],
            },
            generated_at=datetime.now().isoformat(),
        )

    def get_fallback_rotation(self, context: ScheduleContext) -> RotationStrategy:
        """Generate fallback rotation when agent unavailable."""
        return RotationStrategy(
            persona_type="generic",
            weekly_rotation=[
                {"day": "Monday", "primary": "teasing", "secondary": "bundle"},
                {"day": "Tuesday", "primary": "solo", "secondary": "flash_sale"},
                {"day": "Wednesday", "primary": "bundle", "secondary": "winner"},
                {"day": "Thursday", "primary": "sextape", "secondary": "teasing"},
                {"day": "Friday", "primary": "bg", "secondary": "exclusive"},
                {"day": "Saturday", "primary": "winner", "secondary": "bundle"},
                {"day": "Sunday", "primary": "bundle", "secondary": "solo"},
            ],
            spacing_rules={
                "same_type_min_hours": 72,
                "explicit_content_spacing": 48,
                "bundle_frequency": "2x_weekly_max",
            },
            vault_warnings=[],
            generated_at=datetime.now().isoformat(),
        )

    def get_fallback_page_type_rules(self, context: ScheduleContext) -> PageTypeRules:
        """
        Generate fallback page type rules when agent unavailable.

        Context-aware enhancements:
        - Uses performance_tier to adjust base volume targets:
          - Tier 1: +1 to daily targets (high performers can handle more volume)
          - Tier 2: no change (baseline)
          - Tier 3: -1 to daily targets (protect engagement quality)
        """
        profile = context.creator_profile
        is_paid = profile.page_type == "paid" if profile else True

        # Calculate tier-based volume adjustment
        tier_volume_adjustment = 0
        if profile:
            tier = profile.performance_tier
            if tier == 1:
                tier_volume_adjustment = 1  # Tier 1: +1 to daily targets
            elif tier == 3:
                tier_volume_adjustment = -1  # Tier 3: -1 to daily targets
            # Tier 2: no change (tier_volume_adjustment = 0)

        adjustments_made = ["Applied default page type rules"]
        if tier_volume_adjustment != 0:
            adjustments_made.append(
                f"Tier {profile.performance_tier if profile else 2} volume adjustment: "
                f"{'+' if tier_volume_adjustment > 0 else ''}{tier_volume_adjustment}/day"
            )

        if is_paid:
            base_weekly_cap = 5
            base_daily_ppv = 3
            base_daily_bump = 3

            rules = {
                "ppv_weekly_cap": base_weekly_cap
                + (tier_volume_adjustment * 2),  # Weekly scales 2x daily
                "ppv_daily_cap": None,
                "ppv_daily_target": max(2, base_daily_ppv + tier_volume_adjustment),
                "bump_daily_target": max(2, base_daily_bump + tier_volume_adjustment),
                "price_floor": 15,
                "price_ceiling": 50,
                "bump_strategy": "conservative",
                "engagement_focus": "quality_over_quantity",
            }
        else:
            base_daily_cap = 5
            base_daily_ppv = 4
            base_daily_bump = 4

            rules = {
                "ppv_weekly_cap": None,
                "ppv_daily_cap": max(3, base_daily_cap + tier_volume_adjustment),
                "ppv_daily_target": max(3, base_daily_ppv + tier_volume_adjustment),
                "bump_daily_target": max(3, base_daily_bump + tier_volume_adjustment),
                "price_floor": 10,
                "price_ceiling": 35,
                "bump_strategy": "aggressive",
                "engagement_focus": "volume_with_quality",
            }

        return PageTypeRules(
            page_type="paid" if is_paid else "free",
            rules_applied=rules,
            adjustments_made=adjustments_made,
            generated_at=datetime.now().isoformat(),
        )

    def get_fallback_followup(self, ppv_item_id: int, content_type: str) -> FollowUpSequence:
        """Generate fallback follow-up sequence when agent unavailable."""
        return FollowUpSequence(
            ppv_item_id=ppv_item_id,
            sequence=[
                {
                    "touch": 1,
                    "timing_minutes": 25,
                    "strategy": "soft_curiosity",
                    "message": "did u see what i sent?",
                },
                {
                    "touch": 2,
                    "timing_hours": 24,
                    "strategy": "playful_guilt",
                    "message": "some of u didnt open my msg... im not mad just shocked",
                },
                {
                    "touch": 3,
                    "timing_hours": 48,
                    "strategy": "scarcity_close",
                    "message": "taking this down soon babe... last chance",
                },
            ],
            abort_triggers=["negative_response", "spam_report", "unsubscribe"],
        )

    def get_fallback_revenue_projection(self, context: ScheduleContext) -> RevenueProjection:
        """Generate fallback revenue projection when agent unavailable."""
        profile = context.creator_profile
        avg_earnings = profile.current_avg_earnings_per_fan if profile else 5.0
        fan_count = profile.current_active_fans if profile else 1000

        # Simple projection based on historical averages
        weekly_estimate = avg_earnings * fan_count * 0.05  # 5% weekly engagement estimate

        return RevenueProjection(
            schedule_week=context.week_start.isoformat() if context.week_start else "",
            projections={
                "conservative": {"revenue": weekly_estimate * 0.7, "confidence": 0.85},
                "expected": {"revenue": weekly_estimate, "confidence": 0.70},
                "optimistic": {"revenue": weekly_estimate * 1.3, "confidence": 0.55},
            },
            drivers={
                "ppv_revenue": weekly_estimate * 0.8,
                "followup_recovery": weekly_estimate * 0.1,
                "tips_expected": weekly_estimate * 0.1,
            },
            risk_factors=["Projection based on historical averages"],
            opportunity_flags=[],
            generated_at=datetime.now().isoformat(),
        )

    def invoke_pricing_strategist(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[PricingStrategy, bool]:
        """
        Invoke the revenue-optimizer agent for pricing strategy.

        Returns tuple of (PricingStrategy, fallback_used).
        Note: Uses revenue-optimizer (v2.0 consolidated agent).
        """
        agent_name = self._resolve_agent_name("pricing-strategist")  # -> revenue-optimizer
        return self._invoke_with_cache_and_metrics(
            agent_name=agent_name,
            context=context,
            cache_context={"request_type": "pricing_strategy"},
            use_cache=use_cache,
            result_class=PricingStrategy,
            fallback_fn=self.get_fallback_pricing,
            extra_context={"request_type": "pricing_strategy"},
        )

    def invoke_timezone_optimizer(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[TimingStrategy, bool]:
        """
        Invoke the timezone-optimizer agent.

        Returns tuple of (TimingStrategy, fallback_used).
        """
        return self._invoke_with_cache_and_metrics(
            agent_name="timezone-optimizer",
            context=context,
            cache_context={},  # Timezone is primarily creator-specific
            use_cache=use_cache,
            result_class=TimingStrategy,
            fallback_fn=self.get_fallback_timing,
        )

    def invoke_content_rotation_architect(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[RotationStrategy, bool]:
        """
        Invoke the content-strategy-optimizer agent for rotation strategy.

        Returns tuple of (RotationStrategy, fallback_used).
        Note: Uses content-strategy-optimizer (v2.0 consolidated agent).
        """
        agent_name = self._resolve_agent_name("content-rotation-architect")  # -> content-strategy-optimizer
        return self._invoke_with_cache_and_metrics(
            agent_name=agent_name,
            context=context,
            cache_context={"request_type": "rotation_strategy"},
            use_cache=use_cache,
            result_class=RotationStrategy,
            fallback_fn=self.get_fallback_rotation,
        )

    def invoke_page_type_optimizer(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[PageTypeRules, bool]:
        """
        Invoke the volume-calibrator agent for page type rules.

        Returns tuple of (PageTypeRules, fallback_used).
        Note: Uses volume-calibrator (v2.0 consolidated agent).
        """
        agent_name = self._resolve_agent_name("page-type-optimizer")  # -> volume-calibrator
        return self._invoke_with_cache_and_metrics(
            agent_name=agent_name,
            context=context,
            cache_context={"request_type": "page_type_rules"},
            use_cache=use_cache,
            result_class=PageTypeRules,
            fallback_fn=self.get_fallback_page_type_rules,
        )

    def invoke_multi_touch_sequencer(
        self, context: ScheduleContext, ppv_item_id: int, content_type: str
    ) -> tuple[FollowUpSequence, bool]:
        """
        Invoke the multi-touch-sequencer agent.

        Returns tuple of (FollowUpSequence, fallback_used).

        Note: This agent is not cached as follow-ups are PPV-specific.
        """
        agent_name = "multi-touch-sequencer"
        start_time = time.time()

        # Create a fallback closure that captures ppv_item_id and content_type
        def fallback_fn(_ctx: ScheduleContext) -> FollowUpSequence:
            return self.get_fallback_followup(ppv_item_id, content_type)

        if not self.is_agent_available(agent_name):
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                error_msg="Agent not available",
            )
            context.mark_fallback_used(agent_name)
            return fallback_fn(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"ppv_item_id": ppv_item_id, "content_type": content_type}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.metrics.record_invocation(
                        agent_name=agent_name,
                        success=True,
                        time_ms=elapsed_ms,
                    )
                    context.mark_agent_used(agent_name)
                    result = response.result
                    result["ppv_item_id"] = ppv_item_id
                    return FollowUpSequence(**result), False

            self.output_agent_request(request)
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                error_msg="Hybrid mode - awaiting Claude response",
            )
            return fallback_fn(context), True

        # FALLBACK_ONLY MODE
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.record_invocation(
            agent_name=agent_name,
            success=False,
            time_ms=elapsed_ms,
            error_msg="Fallback-only mode",
        )
        context.mark_agent_used(agent_name)
        return fallback_fn(context), True

    def invoke_revenue_forecaster(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[RevenueProjection, bool]:
        """
        Invoke the revenue-optimizer agent for revenue projection.

        Returns tuple of (RevenueProjection, fallback_used).
        Note: Uses revenue-optimizer (v2.0 consolidated agent).
        """
        agent_name = self._resolve_agent_name("revenue-forecaster")  # -> revenue-optimizer
        return self._invoke_with_cache_and_metrics(
            agent_name=agent_name,
            context=context,
            cache_context={"request_type": "revenue_projection"},
            use_cache=use_cache,
            result_class=RevenueProjection,
            fallback_fn=self.get_fallback_revenue_projection,
            extra_context={"request_type": "revenue_projection"},
        )

    def invoke_validation_guardian(
        self, context: ScheduleContext, schedule_items: list[dict[str, Any]]
    ) -> tuple[ValidationResult, bool]:
        """
        Invoke the validation-guardian agent.

        Returns tuple of (ValidationResult, fallback_used).
        Note: Validation is never cached as it depends on schedule_items.
        """
        agent_name = "validation-guardian"
        start_time = time.time()

        # Create a fallback closure that uses schedule_items count
        def create_fallback_result() -> ValidationResult:
            return ValidationResult(
                schedule_id="",
                validation_passed=True,
                errors=[],
                warnings=[],
                stats={"total_items": len(schedule_items), "errors": 0, "warnings": 0},
                auto_fixes_available=[],
                generated_at=datetime.now().isoformat(),
            )

        if not self.is_agent_available(agent_name):
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                error_msg="Agent not available",
            )
            context.mark_fallback_used(agent_name)
            return create_fallback_result(), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"schedule_items": schedule_items}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    elapsed_ms = (time.time() - start_time) * 1000
                    self.metrics.record_invocation(
                        agent_name=agent_name,
                        success=True,
                        time_ms=elapsed_ms,
                    )
                    context.mark_agent_used(agent_name)
                    return ValidationResult(**response.result), False

            self.output_agent_request(request)
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.record_invocation(
                agent_name=agent_name,
                success=False,
                time_ms=elapsed_ms,
                error_msg="Hybrid mode - awaiting Claude response",
            )
            return create_fallback_result(), True

        # FALLBACK_ONLY MODE
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.record_invocation(
            agent_name=agent_name,
            success=False,
            time_ms=elapsed_ms,
            error_msg="Fallback-only mode",
        )
        context.mark_agent_used(agent_name)
        return create_fallback_result(), True

    def invoke_all_agents(
        self, context: ScheduleContext, schedule_items: list[dict[str, Any]] | None = None
    ) -> ScheduleContext:
        """
        Invoke all agents in sequence, populating the context with results.

        This is the main entry point for full agent-enhanced schedule generation.
        Phase 1 agents run in parallel (Haiku - fast), Phase 2+ run sequentially.
        """
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        # Phase 1: Timing and page type (Haiku - fast, PARALLEL)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                timing_future = executor.submit(self.invoke_timezone_optimizer, context)
                page_future = executor.submit(self.invoke_page_type_optimizer, context)

                try:
                    context.timing, timing_fallback = timing_future.result(timeout=20)
                    if timing_fallback:
                        context.mark_fallback_used("timezone-optimizer")
                except FuturesTimeoutError:
                    print("  [AGENT] timezone-optimizer timed out, using fallback", file=sys.stderr)
                    context.timing = self.get_fallback_timing(context)
                    context.mark_fallback_used("timezone-optimizer")

                try:
                    context.page_type_rules, page_fallback = page_future.result(timeout=20)
                    if page_fallback:
                        context.mark_fallback_used("volume-calibrator")
                except FuturesTimeoutError:
                    print("  [AGENT] volume-calibrator timed out, using fallback", file=sys.stderr)
                    context.page_type_rules = self.get_fallback_page_type_rules(context)
                    context.mark_fallback_used("volume-calibrator")
        except Exception as e:
            print(
                f"  [AGENT] Phase 1 parallel execution failed: {e}, using fallbacks",
                file=sys.stderr,
            )
            context.timing = self.get_fallback_timing(context)
            context.page_type_rules = self.get_fallback_page_type_rules(context)
            context.mark_fallback_used("timezone-optimizer")
            context.mark_fallback_used("volume-calibrator")

        # Phase 2: Pricing and rotation (Sonnet - contextual, SEQUENTIAL)
        # These depend on Phase 1 results for context
        context.pricing, _ = self.invoke_pricing_strategist(context)
        context.rotation, _ = self.invoke_content_rotation_architect(context)

        # Phase 3: Revenue projection (Sonnet)
        # Depends on pricing and rotation for accurate projections
        context.revenue_projection, _ = self.invoke_revenue_forecaster(context)

        # Phase 4: Validation (Sonnet - if schedule items provided)
        if schedule_items:
            context.validation_result, _ = self.invoke_validation_guardian(context, schedule_items)

        return context

    # ========================================================================
    # CONTENT TYPE AWARE INVOCATION METHODS (v2.1)
    # ========================================================================

    def invoke_content_strategy_optimizer(
        self,
        creator_id: str,
        page_type: str,
        volume_level: str,
        week_start: date,
        enabled_content_types: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Invoke content-strategy-optimizer agent with content type awareness.

        This method provides the agent with detailed content type metadata
        to enable intelligent content distribution across 20+ content types.

        Args:
            creator_id: The creator's unique identifier
            page_type: Page type ("paid" or "free")
            volume_level: Volume level ("Low", "Mid", "High", "Ultra")
            week_start: Start date of the schedule week
            enabled_content_types: Optional set of content type IDs to use.
                                  If None, all valid types for page_type are used.

        Returns:
            Dict containing:
                - content_distribution: {type_id: weekly_slots}
                - rotation_pattern: List of type_ids for daily rotation
                - priority_order: Ordered list of type_ids by priority
                - daily_schedules: Optional day-by-day breakdown

        Example:
            >>> invoker = AgentInvoker()
            >>> result = invoker.invoke_content_strategy_optimizer(
            ...     creator_id="abc123",
            ...     page_type="paid",
            ...     volume_level="High",
            ...     week_start=date(2025, 1, 6),
            ... )
            >>> print(result['content_distribution'])
            {'ppv': 28, 'bundle': 3, 'vip_post': 2, ...}
        """
        from content_type_registry import REGISTRY

        # Get valid content types for this page
        if enabled_content_types is None:
            valid_types = REGISTRY.get_types_for_page(page_type)
            enabled_content_types = {t.type_id for t in valid_types}
        else:
            # Validate provided types are valid for page
            valid_types = [
                REGISTRY.get(t)
                for t in enabled_content_types
                if t in REGISTRY and REGISTRY.get(t).is_valid_for_page(page_type)
            ]
            enabled_content_types = {t.type_id for t in valid_types}

        # Build context for agent
        context = {
            "creator_id": creator_id,
            "page_type": page_type,
            "volume_level": volume_level,
            "week_start": week_start.isoformat(),
            "enabled_content_types": list(enabled_content_types),
            "content_type_details": [
                {
                    "type_id": t.type_id,
                    "name": t.name,
                    "channel": t.channel,
                    "max_daily": t.max_daily,
                    "max_weekly": t.max_weekly,
                    "min_spacing_hours": t.min_spacing_hours,
                    "priority_tier": t.priority_tier,
                    "has_follow_up": t.has_follow_up,
                    "requires_flyer": t.requires_flyer,
                }
                for t in REGISTRY.get_all()
                if t.type_id in enabled_content_types
            ],
        }

        # Check if agent is available
        agent_name = "content-strategy-optimizer"
        if not self.is_agent_available(agent_name):
            return self._fallback_content_strategy(context)

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            # Create a minimal ScheduleContext for the request
            schedule_context = ScheduleContext(
                creator_id=creator_id,
                week_start=week_start,
                week_end=week_start + timedelta(days=6),
                mode="full",
            )
            request = self.create_agent_request(agent_name, schedule_context, context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    return response.result

            self.output_agent_request(request)

        # Return fallback result
        return self._fallback_content_strategy(context)

    def invoke_validation_guardian_extended(
        self,
        schedule_items: list[dict[str, Any]],
        page_type: str,
        week_start: date,
    ) -> dict[str, Any]:
        """
        Invoke validation-guardian agent with extended rules for 20+ content types.

        This method validates schedules against all business rules including
        page-type-specific content restrictions and spacing requirements.

        Args:
            schedule_items: List of schedule item dicts with content_type, time, etc.
            page_type: Page type ("paid" or "free")
            week_start: Start date of the schedule week

        Returns:
            Dict containing:
                - validation_passed: bool
                - errors: List of critical errors
                - warnings: List of non-critical warnings
                - stats: Validation statistics
                - auto_fixes_available: List of suggested fixes

        Extended Rules Checked:
            - PAGE_TYPE_VIOLATION: Content type not allowed for page
            - VIP_POST_SPACING: VIP posts too close (24h min)
            - LINK_DROP_SPACING: Link drops too close (4h min)
            - ENGAGEMENT_LIMITS: DM/like farm daily limits
            - RETENTION_TIMING: Retention content timing
            - BUNDLE_SPACING: Bundles too close (24h min)
            - GAME_POST_WEEKLY: Game posts 1x/week max
            - BUMP_VARIANT_ROTATION: Bump type variety check
            - CONTENT_TYPE_ROTATION: Same type repeated too often
            - PLACEHOLDER_WARNING: Missing captions for slots
        """
        context = {
            "items": schedule_items,
            "page_type": page_type,
            "week_start": week_start.isoformat(),
            "rules_to_check": [
                "PAGE_TYPE_VIOLATION",
                "VIP_POST_SPACING",
                "LINK_DROP_SPACING",
                "ENGAGEMENT_LIMITS",
                "RETENTION_TIMING",
                "BUNDLE_SPACING",
                "GAME_POST_WEEKLY",
                "BUMP_VARIANT_ROTATION",
                "CONTENT_TYPE_ROTATION",
                "PLACEHOLDER_WARNING",
            ],
        }

        agent_name = "validation-guardian"
        if not self.is_agent_available(agent_name):
            return self._fallback_validation(context)

        # For validation, always use fallback since it's deterministic
        # Agents can enhance with semantic analysis if needed
        return self._fallback_validation(context)

    # ========================================================================
    # FALLBACK STRATEGY METHODS (v2.1)
    # ========================================================================

    def _fallback_content_strategy(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Fallback content strategy when agent unavailable.

        Creates a reasonable content distribution based on:
        - Priority tiers (higher priority = more slots)
        - Volume level (affects total daily/weekly slots)
        - Page type restrictions

        Args:
            context: Dict with page_type, volume_level, enabled_content_types

        Returns:
            Content strategy dict with distribution, rotation, and priority
        """
        from content_type_registry import REGISTRY

        page_type = context.get("page_type", "free")
        volume_level = context.get("volume_level", "Low")
        enabled_types_raw = context.get("enabled_content_types", [])

        # Get valid content types
        if enabled_types_raw:
            enabled_types = set(enabled_types_raw)
            valid_types = [
                REGISTRY.get(t)
                for t in enabled_types
                if t in REGISTRY and REGISTRY.get(t).is_valid_for_page(page_type)
            ]
        else:
            valid_types = REGISTRY.get_types_for_page(page_type)

        # Volume multipliers
        volume_multipliers = {
            "Low": 0.6,
            "Mid": 0.8,
            "High": 1.0,
            "Ultra": 1.2,
        }
        multiplier = volume_multipliers.get(volume_level, 0.8)

        strategy: dict[str, Any] = {
            "content_distribution": {},
            "rotation_pattern": [],
            "priority_order": [],
            "daily_schedules": {},
        }

        # Distribute based on priority tiers
        for content_type in sorted(valid_types, key=lambda t: t.priority_tier):
            # Calculate weekly slots based on priority and volume
            base_slots = content_type.max_weekly
            if content_type.priority_tier == 1:
                # Tier 1: Direct revenue - allocate more
                slots_per_week = min(
                    int(base_slots * multiplier), content_type.max_weekly
                )
            elif content_type.priority_tier == 2:
                # Tier 2: Feed/Wall - moderate allocation
                slots_per_week = min(
                    int(base_slots * multiplier * 0.7), content_type.max_weekly
                )
            elif content_type.priority_tier == 3:
                # Tier 3: Engagement - lower allocation
                slots_per_week = min(
                    int(base_slots * multiplier * 0.5), content_type.max_weekly
                )
            else:
                # Tier 4: Retention - minimal allocation
                slots_per_week = min(
                    int(base_slots * multiplier * 0.3), content_type.max_weekly
                )

            # Ensure at least 1 slot for active types
            slots_per_week = max(1, slots_per_week)

            strategy["content_distribution"][content_type.type_id] = slots_per_week
            strategy["priority_order"].append(content_type.type_id)

        # Build rotation pattern - top 8 types by priority
        strategy["rotation_pattern"] = strategy["priority_order"][:8]

        return strategy

    def _fallback_volume_calibrator(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Fallback volume calculation when agent unavailable.

        Determines appropriate volume level based on fan count.

        Args:
            context: Dict with fan_count key

        Returns:
            Dict with level, ppv_per_day, bump_per_day
        """
        fan_count = context.get("fan_count", 1000)

        if fan_count < 1000:
            return {"level": "Low", "ppv_per_day": 2, "bump_per_day": 2}
        elif fan_count < 5000:
            return {"level": "Mid", "ppv_per_day": 3, "bump_per_day": 3}
        elif fan_count < 15000:
            return {"level": "High", "ppv_per_day": 4, "bump_per_day": 4}
        else:
            return {"level": "Ultra", "ppv_per_day": 5, "bump_per_day": 5}

    def _fallback_validation(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Fallback validation when agent unavailable.

        Performs deterministic rule-based validation using the local
        validate_schedule module.

        Args:
            context: Dict with items, page_type, week_start, rules_to_check

        Returns:
            Validation result dict
        """
        items = context.get("items", [])
        page_type = context.get("page_type", "free")
        rules = context.get("rules_to_check", [])

        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # Import content type registry for validation
        try:
            from content_type_registry import REGISTRY

            # Check PAGE_TYPE_VIOLATION
            if "PAGE_TYPE_VIOLATION" in rules:
                for item in items:
                    ct_id = item.get("content_type") or item.get("content_type_id")
                    if ct_id and ct_id in REGISTRY:
                        ct = REGISTRY.get(ct_id)
                        if not ct.is_valid_for_page(page_type):
                            errors.append(
                                {
                                    "rule": "PAGE_TYPE_VIOLATION",
                                    "message": f"Content type '{ct_id}' not allowed on {page_type} pages",
                                    "item_index": items.index(item),
                                }
                            )

            # Check spacing violations
            type_last_time: dict[str, datetime] = {}
            for item in items:
                ct_id = item.get("content_type") or item.get("content_type_id")
                item_time = item.get("scheduled_time") or item.get("time")
                if not ct_id or not item_time or ct_id not in REGISTRY:
                    continue

                ct = REGISTRY.get(ct_id)
                if isinstance(item_time, str):
                    try:
                        item_dt = datetime.fromisoformat(item_time.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                else:
                    item_dt = item_time

                if ct_id in type_last_time:
                    gap_hours = (item_dt - type_last_time[ct_id]).total_seconds() / 3600
                    if gap_hours < ct.min_spacing_hours:
                        rule_name = f"{ct_id.upper()}_SPACING"
                        if rule_name in rules or "CONTENT_TYPE_ROTATION" in rules:
                            errors.append(
                                {
                                    "rule": rule_name,
                                    "message": f"'{ct_id}' spacing violation: {gap_hours:.1f}h < {ct.min_spacing_hours}h min",
                                    "item_index": items.index(item),
                                }
                            )

                type_last_time[ct_id] = item_dt

            # Check PLACEHOLDER_WARNING
            if "PLACEHOLDER_WARNING" in rules:
                for item in items:
                    if not item.get("caption_id") and not item.get("caption_text"):
                        warnings.append(
                            {
                                "rule": "PLACEHOLDER_WARNING",
                                "message": f"Slot has no caption assigned",
                                "item_index": items.index(item),
                            }
                        )

        except ImportError:
            # Content type registry not available - minimal validation
            warnings.append(
                {
                    "rule": "VALIDATION_LIMITED",
                    "message": "Content type registry unavailable, validation limited",
                }
            )

        return {
            "validation_passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": {
                "total_items": len(items),
                "errors": len(errors),
                "warnings": len(warnings),
                "rules_checked": len(rules),
            },
            "auto_fixes_available": [],
            "generated_at": datetime.now().isoformat(),
        }

    def _fallback_timezone_optimizer(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Fallback timezone optimization when agent unavailable.

        Returns standard EST timing windows optimized for US audiences.

        Args:
            context: Dict with creator_id (optional)

        Returns:
            Timing strategy dict
        """
        return {
            "timezone": "America/New_York",
            "peak_windows": [
                {"start": "18:00", "end": "22:00", "tier": 1, "expected_lift": 1.35},
                {"start": "10:00", "end": "12:00", "tier": 2, "expected_lift": 1.15},
                {"start": "21:00", "end": "23:00", "tier": 1, "expected_lift": 1.30},
            ],
            "avoid_windows": [
                {"start": "03:00", "end": "06:00", "reason": "lowest_engagement"}
            ],
            "best_days": ["Sunday", "Friday", "Saturday"],
            "daily_schedule": {
                "Monday": ["10:00", "18:00", "21:00"],
                "Tuesday": ["10:00", "14:00", "19:00", "22:00"],
                "Wednesday": ["10:00", "18:00", "21:00"],
                "Thursday": ["10:00", "14:00", "19:00", "22:00"],
                "Friday": ["10:00", "18:00", "21:00", "23:00"],
                "Saturday": ["12:00", "18:00", "21:00", "23:00"],
                "Sunday": ["12:00", "18:00", "21:00"],
            },
            "generated_at": datetime.now().isoformat(),
        }

    def get_fallback_for_agent(self, agent_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """
        Get the fallback function for a specific agent.

        This allows external code to access fallback strategies
        without invoking the agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Callable that accepts context dict and returns result dict

        Raises:
            KeyError: If no fallback exists for the agent
        """
        fallback_map: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "content-strategy-optimizer": self._fallback_content_strategy,
            "volume-calibrator": self._fallback_volume_calibrator,
            "validation-guardian": self._fallback_validation,
            "timezone-optimizer": self._fallback_timezone_optimizer,
        }

        if agent_name not in fallback_map:
            raise KeyError(f"No fallback defined for agent: {agent_name}")

        return fallback_map[agent_name]


def main():
    """Test the agent invoker with metrics tracking."""
    from datetime import date

    # Create test context
    context = ScheduleContext(
        creator_id="test_creator",
        week_start=date.today(),
        week_end=date.today() + timedelta(days=6),
        mode="full",
    )

    # Initialize invoker
    invoker = AgentInvoker()

    # Check available agents
    print("Available agents:", invoker.get_available_agents())

    # Test each agent invocation (using v2.0 consolidated agent names)
    print("\nTesting agent invocations:")

    timing, fallback = invoker.invoke_timezone_optimizer(context)
    print(f"  timezone-optimizer: peak_windows={len(timing.peak_windows)}, fallback={fallback}")

    page_rules, fallback = invoker.invoke_page_type_optimizer(context)
    print(
        f"  volume-calibrator (via page-type-optimizer): rules={len(page_rules.rules_applied)}, fallback={fallback}"
    )

    pricing, fallback = invoker.invoke_pricing_strategist(context)
    print(
        f"  revenue-optimizer (via pricing-strategist): prices={len(pricing.content_type_prices)}, fallback={fallback}"
    )

    rotation, fallback = invoker.invoke_content_rotation_architect(context)
    print(
        f"  content-strategy-optimizer (via content-rotation-architect): rotation={len(rotation.weekly_rotation)}, fallback={fallback}"
    )

    revenue, fallback = invoker.invoke_revenue_forecaster(context)
    print(
        f"  revenue-optimizer (via revenue-forecaster): projections={len(revenue.projections)}, fallback={fallback}"
    )

    followup, fallback = invoker.invoke_multi_touch_sequencer(context, 1, "solo")
    print(f"  multi-touch-sequencer: touches={len(followup.sequence)}, fallback={fallback}")

    validation, fallback = invoker.invoke_validation_guardian(context, [])
    print(f"  validation-guardian: passed={validation.validation_passed}, fallback={fallback}")

    # Test full invocation
    print("\nFull agent invocation:")
    context = invoker.invoke_all_agents(context)
    print(f"  Agents used: {context.agents_used}")
    print(f"  Fallbacks used: {context.fallbacks_used}")

    # Display metrics summary
    print("\n" + "=" * 60)
    print("AGENT METRICS SUMMARY")
    print("=" * 60)
    metrics = invoker.get_metrics_summary()
    print(f"Total invocations: {metrics['total_invocations']}")
    print(f"Total fallbacks: {metrics['total_fallbacks']}")
    print(f"Total cache hits: {metrics['total_cache_hits']}")
    print(f"Overall fallback rate: {metrics['overall_fallback_rate']:.1%}")
    print(f"Overall cache hit rate: {metrics['overall_cache_hit_rate']:.1%}")

    print("\nPer-agent breakdown:")
    for agent_name, agent_stats in metrics["agents"].items():
        print(f"  {agent_name}:")
        print(f"    Invocations: {agent_stats['invocations']}")
        print(f"    Fallback rate: {agent_stats['fallback_rate']:.1%}")
        print(f"    Cache hit rate: {agent_stats['cache_hit_rate']:.1%}")
        print(f"    Avg time: {agent_stats['avg_time_ms']:.2f}ms")
        if agent_stats.get("recent_errors"):
            print(f"    Recent errors: {agent_stats['recent_errors']}")


if __name__ == "__main__":
    main()
