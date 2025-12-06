"""
Agent Invoker for EROS Schedule Generator.

This module provides utilities for invoking specialized sub-agents during
schedule generation. It handles agent discovery, invocation, caching,
timeout management, and fallback behavior.

Designed for use with Claude Code's native agent system.
"""

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shared_context import (
    AgentInvokerMode,
    AgentRequest,
    AgentResponse,
    FollowUpSequence,
    PageTypeRules,
    PersonaProfile,
    PipelineState,
    PricingStrategy,
    RevenueProjection,
    RotationStrategy,
    ScheduleContext,
    TimingStrategy,
    ValidationResult,
)


@dataclass
class AgentConfig:
    """Configuration for a sub-agent."""

    name: str
    model: str  # haiku, sonnet, opus
    timeout_seconds: int
    cache_duration_days: int
    tools: list[str]


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
        model="sonnet",
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

    def _find_database(self) -> str:
        """Find the EROS database path with proper env var priority."""
        # Priority 1: Environment variable
        env_path = os.environ.get("EROS_DATABASE_PATH", "")
        if env_path:
            env_db = Path(env_path)
            if env_db.exists():
                return str(env_db)
            # Warn but continue to fallbacks
            print(f"  [WARNING] EROS_DATABASE_PATH={env_path} not found, trying fallbacks", file=sys.stderr)

        # Priority 2-4: Standard locations
        fallback_paths = [
            Path.home() / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
            Path.home() / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
            Path.home() / ".eros" / "eros.db",
        ]

        for path in fallback_paths:
            if path.exists():
                return str(path)

        raise FileNotFoundError("EROS database not found. Set EROS_DATABASE_PATH or place database at ~/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db")

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, agent_name: str, context: dict[str, Any]) -> str:
        """Generate a cache key for an agent invocation."""
        context_str = json.dumps(context, sort_keys=True, default=str)
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
        invoke_fn,
        fallback_fn,
        context: ScheduleContext,
        max_retries: int = 2,
    ) -> tuple[Any, bool]:
        """
        Invoke an agent with retry logic and fallback chain.

        Args:
            agent_name: Name of the agent being invoked
            invoke_fn: Function to invoke (should return (result, fallback_used))
            fallback_fn: Function to get fallback value (should return result)
            context: Schedule context
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (result, fallback_used)
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                result, fallback_used = invoke_fn(context)

                # Validate the result has expected structure
                if result is not None and not fallback_used:
                    if self._validate_agent_output(agent_name, result):
                        return result, False
                    print(f"  [AGENT] {agent_name} output validation failed, retrying...", file=sys.stderr)
                else:
                    return result, fallback_used

            except Exception as e:
                last_error = e
                print(f"  [AGENT] {agent_name} attempt {attempt + 1}/{max_retries} failed: {e}", file=sys.stderr)

        # All retries exhausted - use fallback
        if last_error:
            print(f"  [AGENT] {agent_name} failed after {max_retries} attempts, using fallback", file=sys.stderr)

        context.mark_fallback_used(agent_name)
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
                return hasattr(result, 'peak_windows') and hasattr(result, 'timezone')
            elif agent_name == "volume-calibrator":
                return hasattr(result, 'rules_applied') and hasattr(result, 'page_type')
            elif agent_name == "revenue-optimizer":
                return hasattr(result, 'content_type_prices') or hasattr(result, 'projections')
            elif agent_name == "content-strategy-optimizer":
                return hasattr(result, 'weekly_rotation')
            elif agent_name == "multi-touch-sequencer":
                return hasattr(result, 'sequence')
            elif agent_name == "validation-guardian":
                return hasattr(result, 'validation_passed')
            else:
                return True  # Unknown agent, assume valid
        except Exception:
            return False

    # ========================================================================
    # FALLBACK METHODS
    # ========================================================================

    def get_fallback_pricing(self, context: ScheduleContext) -> PricingStrategy:
        """Generate fallback pricing when agent unavailable."""
        # Default tier-based pricing
        profile = context.creator_profile
        is_paid = profile.page_type == "paid" if profile else True

        base_prices = {
            "solo": 15.0 if is_paid else 12.0,
            "bundle": 25.0 if is_paid else 20.0,
            "sextape": 30.0 if is_paid else 25.0,
            "bg": 35.0 if is_paid else 30.0,
            "winner": 20.0 if is_paid else 15.0,
            "custom": 40.0 if is_paid else 35.0,
        }

        return PricingStrategy(
            content_type_prices={
                ct: {"base": price, "optimized": price, "reasoning": "Default tier pricing"}
                for ct, price in base_prices.items()
            },
            page_type_modifier=1.0 if is_paid else 0.85,
            weekly_revenue_projection=0.0,
            generated_at=datetime.now().isoformat(),
        )

    def get_fallback_timing(self, context: ScheduleContext) -> TimingStrategy:
        """Generate fallback timing when agent unavailable."""
        return TimingStrategy(
            timezone="America/New_York",
            peak_windows=[
                {"start": "18:00", "end": "22:00", "tier": 1, "expected_lift": 1.35},
                {"start": "10:00", "end": "12:00", "tier": 2, "expected_lift": 1.15},
            ],
            avoid_windows=[
                {"start": "03:00", "end": "06:00", "reason": "lowest_engagement"}
            ],
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
        """Generate fallback page type rules when agent unavailable."""
        profile = context.creator_profile
        is_paid = profile.page_type == "paid" if profile else True

        if is_paid:
            rules = {
                "ppv_weekly_cap": 5,
                "ppv_daily_cap": None,
                "price_floor": 15,
                "price_ceiling": 50,
                "bump_strategy": "conservative",
                "engagement_focus": "quality_over_quantity",
            }
        else:
            rules = {
                "ppv_weekly_cap": None,
                "ppv_daily_cap": 5,
                "price_floor": 10,
                "price_ceiling": 35,
                "bump_strategy": "aggressive",
                "engagement_focus": "volume_with_quality",
            }

        return PageTypeRules(
            page_type="paid" if is_paid else "free",
            rules_applied=rules,
            adjustments_made=["Applied default page type rules"],
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
        legacy_name = "pricing-strategist"
        agent_name = self._resolve_agent_name(legacy_name)  # -> revenue-optimizer
        cache_context = {"creator_id": context.creator_id, "week": str(context.week_start)}
        cache_key = self._get_cache_key(agent_name, cache_context)

        # Check cache first
        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                return PricingStrategy(**cached), False

        # Check if agent is available
        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_pricing(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"request_type": "pricing_strategy"}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return PricingStrategy(**response.result), False

            self.output_agent_request(request)
            return self.get_fallback_pricing(context), True

        context.mark_agent_used(agent_name)
        return self.get_fallback_pricing(context), True

    def invoke_timezone_optimizer(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[TimingStrategy, bool]:
        """
        Invoke the timezone-optimizer agent.

        Returns tuple of (TimingStrategy, fallback_used).
        """
        agent_name = "timezone-optimizer"
        cache_context = {"creator_id": context.creator_id}
        cache_key = self._get_cache_key(agent_name, cache_context)

        # Check cache first
        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                return TimingStrategy(**cached), False

        # Check if agent is available
        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_timing(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            request = self.create_agent_request(agent_name, context)
            self.pending_requests.append(request)

            # Check if we already have a response (resume mode)
            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return TimingStrategy(**response.result), False

            # Output request for Claude and return fallback for now
            self.output_agent_request(request)
            return self.get_fallback_timing(context), True

        # FALLBACK_ONLY MODE: Use fallback
        context.mark_agent_used(agent_name)
        return self.get_fallback_timing(context), True

    def invoke_content_rotation_architect(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[RotationStrategy, bool]:
        """
        Invoke the content-strategy-optimizer agent for rotation strategy.

        Returns tuple of (RotationStrategy, fallback_used).
        Note: Uses content-strategy-optimizer (v2.0 consolidated agent).
        """
        legacy_name = "content-rotation-architect"
        agent_name = self._resolve_agent_name(legacy_name)  # -> content-strategy-optimizer
        cache_context = {"creator_id": context.creator_id, "week": str(context.week_start)}
        cache_key = self._get_cache_key(agent_name, cache_context)

        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                return RotationStrategy(**cached), False

        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_rotation(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            request = self.create_agent_request(agent_name, context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return RotationStrategy(**response.result), False

            self.output_agent_request(request)
            return self.get_fallback_rotation(context), True

        context.mark_agent_used(agent_name)
        return self.get_fallback_rotation(context), True

    def invoke_page_type_optimizer(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[PageTypeRules, bool]:
        """
        Invoke the volume-calibrator agent for page type rules.

        Returns tuple of (PageTypeRules, fallback_used).
        Note: Uses volume-calibrator (v2.0 consolidated agent).
        """
        legacy_name = "page-type-optimizer"
        agent_name = self._resolve_agent_name(legacy_name)  # -> volume-calibrator
        cache_context = {"creator_id": context.creator_id}
        cache_key = self._get_cache_key(agent_name, cache_context)

        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                return PageTypeRules(**cached), False

        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_page_type_rules(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            request = self.create_agent_request(agent_name, context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return PageTypeRules(**response.result), False

            self.output_agent_request(request)
            return self.get_fallback_page_type_rules(context), True

        context.mark_agent_used(agent_name)
        return self.get_fallback_page_type_rules(context), True

    def invoke_multi_touch_sequencer(
        self, context: ScheduleContext, ppv_item_id: int, content_type: str
    ) -> tuple[FollowUpSequence, bool]:
        """
        Invoke the multi-touch-sequencer agent.

        Returns tuple of (FollowUpSequence, fallback_used).
        """
        agent_name = "multi-touch-sequencer"

        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_followup(ppv_item_id, content_type), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"ppv_item_id": ppv_item_id, "content_type": content_type}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    result = response.result
                    result["ppv_item_id"] = ppv_item_id
                    return FollowUpSequence(**result), False

            self.output_agent_request(request)
            return self.get_fallback_followup(ppv_item_id, content_type), True

        context.mark_agent_used(agent_name)
        return self.get_fallback_followup(ppv_item_id, content_type), True

    def invoke_revenue_forecaster(
        self, context: ScheduleContext, use_cache: bool = True
    ) -> tuple[RevenueProjection, bool]:
        """
        Invoke the revenue-optimizer agent for revenue projection.

        Returns tuple of (RevenueProjection, fallback_used).
        Note: Uses revenue-optimizer (v2.0 consolidated agent).
        """
        legacy_name = "revenue-forecaster"
        agent_name = self._resolve_agent_name(legacy_name)  # -> revenue-optimizer
        cache_context = {"creator_id": context.creator_id, "week": str(context.week_start)}
        cache_key = self._get_cache_key(agent_name, cache_context)

        if use_cache:
            cached = self._get_cached_result(agent_name, cache_key)
            if cached:
                return RevenueProjection(**cached), False

        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return self.get_fallback_revenue_projection(context), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"request_type": "revenue_projection"}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return RevenueProjection(**response.result), False

            self.output_agent_request(request)
            return self.get_fallback_revenue_projection(context), True

        context.mark_agent_used(agent_name)
        return self.get_fallback_revenue_projection(context), True

    def invoke_validation_guardian(
        self, context: ScheduleContext, schedule_items: list[dict[str, Any]]
    ) -> tuple[ValidationResult, bool]:
        """
        Invoke the validation-guardian agent.

        Returns tuple of (ValidationResult, fallback_used).
        Note: Validation is never cached.
        """
        agent_name = "validation-guardian"

        if not self.is_agent_available(agent_name):
            context.mark_fallback_used(agent_name)
            return ValidationResult(
                schedule_id="",
                validation_passed=True,
                errors=[],
                warnings=[],
                stats={"total_items": len(schedule_items), "errors": 0, "warnings": 0},
                auto_fixes_available=[],
                generated_at=datetime.now().isoformat(),
            ), True

        # HYBRID MODE: Output request for Claude to invoke
        if self.mode == AgentInvokerMode.HYBRID:
            extra_context = {"schedule_items": schedule_items}
            request = self.create_agent_request(agent_name, context, extra_context)
            self.pending_requests.append(request)

            if request.request_id in self.received_responses:
                response = self.received_responses[request.request_id]
                if response.success and response.result:
                    context.mark_agent_used(agent_name)
                    return ValidationResult(**response.result), False

            self.output_agent_request(request)
            return ValidationResult(
                schedule_id="",
                validation_passed=True,
                errors=[],
                warnings=[],
                stats={"total_items": len(schedule_items), "errors": 0, "warnings": 0},
                auto_fixes_available=[],
                generated_at=datetime.now().isoformat(),
            ), True

        context.mark_agent_used(agent_name)
        return ValidationResult(
            schedule_id="",
            validation_passed=True,
            errors=[],
            warnings=[],
            stats={"total_items": len(schedule_items), "errors": 0, "warnings": 0},
            auto_fixes_available=[],
            generated_at=datetime.now().isoformat(),
        ), True

    def invoke_all_agents(
        self, context: ScheduleContext, schedule_items: list[dict[str, Any]] | None = None
    ) -> ScheduleContext:
        """
        Invoke all agents in sequence, populating the context with results.

        This is the main entry point for full agent-enhanced schedule generation.
        Phase 1 agents run in parallel (Haiku - fast), Phase 2+ run sequentially.
        """
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

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
            print(f"  [AGENT] Phase 1 parallel execution failed: {e}, using fallbacks", file=sys.stderr)
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


def main():
    """Test the agent invoker."""
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
    print(f"  volume-calibrator (via page-type-optimizer): rules={len(page_rules.rules_applied)}, fallback={fallback}")

    pricing, fallback = invoker.invoke_pricing_strategist(context)
    print(f"  revenue-optimizer (via pricing-strategist): prices={len(pricing.content_type_prices)}, fallback={fallback}")

    rotation, fallback = invoker.invoke_content_rotation_architect(context)
    print(f"  content-strategy-optimizer (via content-rotation-architect): rotation={len(rotation.weekly_rotation)}, fallback={fallback}")

    revenue, fallback = invoker.invoke_revenue_forecaster(context)
    print(f"  revenue-optimizer (via revenue-forecaster): projections={len(revenue.projections)}, fallback={fallback}")

    followup, fallback = invoker.invoke_multi_touch_sequencer(context, 1, "solo")
    print(f"  multi-touch-sequencer: touches={len(followup.sequence)}, fallback={fallback}")

    validation, fallback = invoker.invoke_validation_guardian(context, [])
    print(f"  validation-guardian: passed={validation.validation_passed}, fallback={fallback}")

    # Test full invocation
    print("\nFull agent invocation:")
    context = invoker.invoke_all_agents(context)
    print(f"  Agents used: {context.agents_used}")
    print(f"  Fallbacks used: {context.fallbacks_used}")


if __name__ == "__main__":
    main()
