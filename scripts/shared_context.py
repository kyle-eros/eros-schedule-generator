"""
Shared context dataclass for inter-agent communication in EROS Schedule Generator.

This module defines the ScheduleContext that is passed between specialized agents
during schedule generation, allowing them to share data and accumulated results.

Also includes data structures for hybrid agent invocation (Phase 2).
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class AgentInvokerMode(Enum):
    """Mode for agent invocation."""

    FALLBACK_ONLY = "fallback"  # Always use fallback values (current behavior)
    HYBRID = "hybrid"  # Output requests for Claude to invoke, then resume


@dataclass(frozen=False)
class AgentRequest:
    """
    Request for Claude to invoke a sub-agent.

    This is output by Python when running in HYBRID mode, signaling that
    Claude should invoke the specified agent via Task tool.
    """

    request_id: str  # Unique ID for matching response (e.g., "req_timezone_a1b2c3d4")
    agent_name: str  # Must match file in ~/.claude/agents/eros-scheduling/{name}.md
    agent_model: str  # haiku, sonnet, opus
    timeout_seconds: int
    context: dict[str, Any]  # Input data for agent
    expected_output_schema: str  # Name of expected output type (e.g., "TimingStrategy")
    cache_key: str | None = None  # For caching (None = don't cache)


@dataclass(frozen=False)
class AgentResponse:
    """
    Response from a sub-agent invocation.

    Written by Claude after invoking an agent, read by Python on resume.
    """

    request_id: str  # Matches the request_id from AgentRequest
    agent_name: str
    success: bool
    result: dict[str, Any] | None = None  # Agent output parsed as dict
    error: str | None = None  # Error message if success=False
    fallback_used: bool = False  # True if fallback was used instead of agent
    execution_time_ms: int = 0
    cached: bool = False


@dataclass(frozen=False)
class PipelineState:
    """
    State for pipeline pause/resume in hybrid mode.

    Saved to disk when pipeline pauses for agent invocation,
    loaded on resume to continue from where we left off.
    """

    session_id: str
    creator_id: str
    week: str
    mode: str  # "hybrid"
    current_step: str  # "1", "3", "8", "10" - corresponds to agent phases
    completed_steps: list[str] = field(default_factory=list)
    pending_agent_requests: list[dict[str, Any]] = field(default_factory=list)
    received_agent_responses: list[dict[str, Any]] = field(default_factory=list)
    partial_schedule_items: list[dict[str, Any]] = field(default_factory=list)
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "session_id": self.session_id,
            "creator_id": self.creator_id,
            "week": self.week,
            "mode": self.mode,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "pending_agent_requests": self.pending_agent_requests,
            "received_agent_responses": self.received_agent_responses,
            "partial_schedule_items": self.partial_schedule_items,
            "context_snapshot": self.context_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineState":
        """Deserialize from JSON storage."""
        return cls(
            session_id=data.get("session_id", ""),
            creator_id=data.get("creator_id", ""),
            week=data.get("week", ""),
            mode=data.get("mode", "hybrid"),
            current_step=data.get("current_step", "0"),
            completed_steps=data.get("completed_steps", []),
            pending_agent_requests=data.get("pending_agent_requests", []),
            received_agent_responses=data.get("received_agent_responses", []),
            partial_schedule_items=data.get("partial_schedule_items", []),
            context_snapshot=data.get("context_snapshot", {}),
        )


@dataclass(frozen=False)
class CreatorProfile:
    """Creator profile data loaded from database."""

    creator_id: str
    page_name: str
    display_name: str
    page_type: str  # "paid" or "free"
    subscription_price: float
    current_active_fans: int
    performance_tier: int  # 1, 2, or 3
    current_total_earnings: float
    current_avg_spend_per_txn: float
    current_avg_earnings_per_fan: float

    # Volume settings
    volume_level: str = "Mid"  # Low, Mid, High, Ultra
    ppv_per_day: int = 3
    bump_per_day: int = 3


@dataclass(frozen=False)
class PersonaProfile:
    """Creator persona for voice/tone matching."""

    creator_id: str
    primary_tone: str  # playful, seductive, aggressive, etc.
    emoji_frequency: str  # none, light, moderate, heavy
    favorite_emojis: str
    slang_level: str  # none, light, heavy
    avg_sentiment: float
    avg_caption_length: int


@dataclass(frozen=False)
class PricingStrategy:
    """Output from pricing-strategist agent."""

    content_type_prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Format: {"solo": {"base": 15, "optimized": 18, "reasoning": "..."}}
    page_type_modifier: float = 1.0
    weekly_revenue_projection: float = 0.0
    generated_at: str = ""


@dataclass(frozen=False)
class TimingStrategy:
    """Output from timezone-optimizer agent."""

    timezone: str = "America/New_York"
    peak_windows: list[dict[str, Any]] = field(default_factory=list)
    # Format: [{"start": "18:00", "end": "22:00", "tier": 1, "expected_lift": 1.35}]
    avoid_windows: list[dict[str, Any]] = field(default_factory=list)
    best_days: list[str] = field(default_factory=list)
    daily_schedule: dict[str, list[str]] = field(default_factory=dict)
    # Format: {"Monday": ["10:00", "18:00", "21:00"]}
    generated_at: str = ""


@dataclass(frozen=False)
class RotationStrategy:
    """Output from content-rotation-architect agent."""

    persona_type: str = ""
    weekly_rotation: list[dict[str, Any]] = field(default_factory=list)
    # Format: [{"day": "Monday", "primary": "teasing", "secondary": "bundle"}]
    spacing_rules: dict[str, Any] = field(default_factory=dict)
    vault_warnings: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class FollowUpSequence:
    """Output from multi-touch-sequencer agent for a single PPV."""

    ppv_item_id: int = 0
    sequence: list[dict[str, Any]] = field(default_factory=list)
    # Format: [{"touch": 1, "timing_minutes": 20, "strategy": "soft_curiosity", "message": "..."}]
    abort_triggers: list[str] = field(default_factory=list)


@dataclass(frozen=False)
class RevenueProjection:
    """Output from revenue-forecaster agent."""

    schedule_week: str = ""
    projections: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Format: {"conservative": {"revenue": 850, "confidence": 0.85}}
    drivers: dict[str, float] = field(default_factory=dict)
    risk_factors: list[str] = field(default_factory=list)
    opportunity_flags: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class PageTypeRules:
    """Output from page-type-optimizer agent."""

    page_type: str = ""
    rules_applied: dict[str, Any] = field(default_factory=dict)
    # Format: {"ppv_weekly_cap": 5, "price_floor": 15, "bump_strategy": "conservative"}
    adjustments_made: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class ValidationResult:
    """Output from validation-guardian agent."""

    schedule_id: str = ""
    validation_passed: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    auto_fixes_available: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class ScheduleContext:
    """
    Master context object passed between all agents during schedule generation.

    This accumulates data from each agent in the pipeline, allowing downstream
    agents to leverage insights from upstream agents.
    """

    # Core identifiers
    creator_id: str
    week_start: date
    week_end: date

    # Input data from database
    creator_profile: CreatorProfile | None = None
    persona_profile: PersonaProfile | None = None

    # Agent outputs (accumulated during pipeline)
    pricing: PricingStrategy | None = None
    timing: TimingStrategy | None = None
    rotation: RotationStrategy | None = None
    followup_sequences: list[FollowUpSequence] = field(default_factory=list)
    revenue_projection: RevenueProjection | None = None
    page_type_rules: PageTypeRules | None = None
    validation_result: ValidationResult | None = None

    # Pipeline metadata
    mode: str = "quick"  # "quick" or "full"
    agents_used: list[str] = field(default_factory=list)
    fallbacks_used: list[str] = field(default_factory=list)
    execution_start: str = ""
    execution_end: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "creator_id": self.creator_id,
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_end": self.week_end.isoformat() if self.week_end else None,
            "mode": self.mode,
            "agents_used": self.agents_used,
            "fallbacks_used": self.fallbacks_used,
            "has_pricing": self.pricing is not None,
            "has_timing": self.timing is not None,
            "has_rotation": self.rotation is not None,
            "has_followups": len(self.followup_sequences) > 0,
            "has_revenue_projection": self.revenue_projection is not None,
            "has_page_type_rules": self.page_type_rules is not None,
            "has_validation": self.validation_result is not None,
        }

    def mark_agent_used(self, agent_name: str) -> None:
        """Record that an agent was successfully invoked."""
        if agent_name not in self.agents_used:
            self.agents_used.append(agent_name)

    def mark_fallback_used(self, agent_name: str) -> None:
        """Record that a fallback was used instead of an agent."""
        if agent_name not in self.fallbacks_used:
            self.fallbacks_used.append(agent_name)
