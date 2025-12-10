#!/usr/bin/env python3
"""
EROS Schedule Generator - Centralized Data Models

This module contains all dataclasses and Pydantic models used across the
schedule generation pipeline. All modules should import models from here
to ensure consistency and prevent circular dependencies.

Module Organization:
    1. Enums - Status, content type, and validation enums
    2. Core Dataclasses - Primary data structures for scheduling
    3. Agent/Pipeline Dataclasses - Sub-agent integration models
    4. Validation Dataclasses - Validation result models
    5. Pydantic Models - API boundary validation

Usage:
    from models import (
        ScheduleConfig,
        CreatorProfile,
        Caption,
        ScheduleItem,
        ScheduleResult,
        ValidationIssue,
        ScheduleRequest,
        ScheduleResponse,
    )
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional

# =============================================================================
# ENUMS
# =============================================================================


class SlotType(str, Enum):
    """Types of schedule slots."""

    PPV = "ppv"
    BUMP = "bump"
    FOLLOW_UP = "follow_up"
    WALL_POST = "wall_post"
    FREE_PREVIEW = "free_preview"
    POLL = "poll"
    GAME_WHEEL = "game_wheel"
    DRIP = "drip"


class ContentChannel(str, Enum):
    """Distribution channels for content."""

    MASS_MESSAGE = "mass_message"
    CAMPAIGN = "campaign"
    DIRECT_UNLOCK = "direct_unlock"
    FEED = "feed"
    POLL = "poll"
    GAMIFICATION = "gamification"


class PageType(str, Enum):
    """OnlyFans page subscription type."""

    PAID = "paid"
    FREE = "free"


class VolumeLevel(str, Enum):
    """Volume level tiers for PPV scheduling."""

    BASE = "Base"
    LOW = "Low"
    MID = "Mid"
    GROWTH = "Growth"
    SCALE = "Scale"
    HIGH = "High"
    ULTRA = "Ultra"


class Severity(str, Enum):
    """Validation issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AgentInvokerMode(str, Enum):
    """Mode for agent invocation in hybrid pipeline."""

    FALLBACK_ONLY = "fallback"  # Always use fallback values (current behavior)
    HYBRID = "hybrid"  # Output requests for Claude to invoke, then resume


# =============================================================================
# CORE DATACLASSES - Schedule Generation
# =============================================================================


@dataclass(frozen=True, slots=True)
class ScheduleConfig:
    """
    Configuration for schedule generation.

    This is the primary input configuration for the schedule generation pipeline.
    It controls all aspects of schedule creation including volume, timing, and
    content type enablement.

    Attributes:
        creator_id: Unique identifier for the creator.
        creator_name: Display name (page_name) for the creator.
        page_type: Subscription type ("paid" or "free").
        week_start: Start date of the scheduling week (Monday).
        week_end: End date of the scheduling week (Sunday).
        volume_level: Volume tier (Base, Low, Mid, High, Ultra).
        ppv_per_day: Target PPV messages per day.
        bump_per_day: Target bump/follow-up messages per day.
        min_freshness: Minimum freshness score for caption selection.
        performance_weight: Weight for performance score in selection.
        freshness_weight: Weight for freshness score in selection.
        min_ppv_spacing_hours: Minimum hours between PPV messages.
        enable_follow_ups: Whether to generate follow-up messages.
        enable_drip_windows: Whether to enforce no-PPV drip windows.
        enable_page_type_rules: Whether to apply page type specific rules.
        mode: Pipeline mode ("quick" or "full").
    """

    creator_id: str
    creator_name: str
    page_type: str  # "paid" or "free"
    week_start: date
    week_end: date
    volume_level: str = "Mid"
    ppv_per_day: int = 4
    bump_per_day: int = 4
    min_freshness: float = 30.0
    performance_weight: float = 0.6
    freshness_weight: float = 0.4
    min_ppv_spacing_hours: int = 3
    enable_follow_ups: bool = True
    enable_drip_windows: bool = False
    enable_page_type_rules: bool = True
    # Volume optimization fields
    volume_period: str = "day"  # "day" or "week"
    ppv_per_week: int = 0  # Weekly total for tracking
    is_paid_page: bool = False  # Convenience flag
    # Enhanced pipeline mode fields
    mode: str = "full"  # "quick" or "full"
    use_quality_scoring: bool = False  # Enable LLM quality scoring
    use_caption_enhancement: bool = False  # Enable caption enhancement
    use_context_followups: bool = False  # Enable context-aware follow-ups
    use_agents: bool = False  # Enable sub-agent delegation
    # Content type toggles
    enable_wall_posts: bool = False
    wall_posts_per_day: int = 2
    enable_free_previews: bool = False
    previews_per_day: int = 1
    enable_polls: bool = False
    polls_per_week: int = 3
    enable_game_wheel: bool = False
    wall_post_hours: tuple[int, ...] = (12, 16, 20)
    preview_lead_time_hours: int = 2
    # Earnings-based selection config
    earnings_weight: float = 0.70
    earnings_freshness_weight: float = 0.20
    persona_tiebreak_weight: float = 0.10
    reserved_slot_ratio: float = 0.15
    min_uses_for_tested: int = 3
    # Extended content types
    enabled_content_types: frozenset[str] = frozenset()
    live_schedule: tuple[datetime, ...] | None = None


@dataclass(slots=True)
class CreatorProfile:
    """
    Creator profile data from database.

    Contains all information needed to generate a personalized schedule
    for a creator, including persona data, vault availability, and
    performance history.

    Attributes:
        creator_id: Unique identifier for the creator.
        page_name: Creator's page name (used for lookups).
        display_name: Display name shown to users.
        page_type: Subscription type ("paid" or "free").
        active_fans: Current number of active fans.
        volume_level: Current volume tier setting.
        primary_tone: Primary voice tone for persona matching.
        emoji_frequency: Emoji usage level.
        slang_level: Slang usage level.
        avg_sentiment: Average sentiment score (0.0-1.0).
        best_hours: List of optimal posting hours.
        vault_types: List of content type IDs in vault.
        content_notes: Parsed JSON notes from creators table.
        filter_keywords: Keywords to filter from caption selection.
        price_modifiers: Price modifiers by content type.
    """

    creator_id: str
    page_name: str
    display_name: str
    page_type: str
    active_fans: int
    volume_level: str
    primary_tone: str
    emoji_frequency: str
    slang_level: str
    avg_sentiment: float
    best_hours: list[int] = field(default_factory=list)
    vault_types: list[int] = field(default_factory=list)
    content_notes: dict = field(default_factory=dict)
    filter_keywords: set = field(default_factory=set)
    price_modifiers: dict = field(default_factory=dict)


@dataclass(slots=True)
class Caption:
    """
    Caption data for selection.

    Represents a caption from the captions table with all scoring
    and persona matching data needed for selection.

    Attributes:
        caption_id: Unique caption identifier.
        caption_text: The actual caption text.
        caption_type: Type classification (ppv, follow_up, etc.).
        content_type_id: Foreign key to content types.
        content_type_name: Human-readable content type name.
        performance_score: Historical performance score (0-100).
        freshness_score: Freshness score (0-100, higher = fresher).
        tone: Detected tone for persona matching.
        emoji_style: Emoji usage style.
        slang_level: Slang usage level.
        is_universal: Whether caption works for all creators.
        combined_score: Weighted combination of scores.
        persona_boost: Multiplier from persona matching (1.0-1.4).
        final_weight: Final selection weight.
        creator_avg_earnings: Creator-specific average earnings.
        global_avg_earnings: Global average earnings (fallback).
        creator_times_used: Times used by this creator.
        global_times_used: Global usage count.
        earnings_source: Source of earnings data.
        is_untested: True if < min_uses_for_tested.
    """

    caption_id: int
    caption_text: str
    caption_type: str
    content_type_id: int | None
    content_type_name: str | None
    performance_score: float
    freshness_score: float
    tone: str | None
    emoji_style: str | None
    slang_level: str | None
    is_universal: bool
    combined_score: float = 0.0
    persona_boost: float = 1.0
    final_weight: float = 0.0
    # Earnings-based fields
    creator_avg_earnings: float | None = None
    global_avg_earnings: float | None = None
    creator_times_used: int = 0
    global_times_used: int = 0
    earnings_source: str = "none"
    is_untested: bool = False


@dataclass(slots=True)
class ScheduleItem:
    """
    Represents a scheduled content item.

    The primary output unit of the schedule generation pipeline.
    Each item represents a single piece of content to be sent at
    a specific time.

    Attributes:
        item_id: Unique identifier for this schedule item.
        creator_id: Creator this item belongs to.
        scheduled_date: Date in YYYY-MM-DD format.
        scheduled_time: Time in HH:MM format.
        item_type: Type of item (ppv, bump, wall_post, etc.).
        channel: Distribution channel (mass_message, feed, etc.).
        caption_id: Foreign key to captions table.
        caption_text: The actual caption text.
        content_type_id: Foreign key to content types.
        content_type_name: Human-readable content type.
        suggested_price: Recommended price for PPV.
        freshness_score: Caption freshness at time of scheduling.
        performance_score: Caption performance score.
        is_follow_up: Whether this is a follow-up message.
        parent_item_id: ID of parent item if follow-up.
        status: Current status (pending, sent, etc.).
        priority: Priority level (1-5, 1=highest).
        notes: Additional notes for this item.
    """

    item_id: int
    creator_id: str
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str  # HH:MM
    item_type: str  # ppv, bump, wall_post, drip, free_preview, poll, game_wheel
    channel: str = "mass_message"
    caption_id: int | None = None
    caption_text: str | None = None
    content_type_id: int | None = None
    content_type_name: str | None = None
    suggested_price: float | None = None
    freshness_score: float = 100.0
    performance_score: float = 50.0
    is_follow_up: bool = False
    parent_item_id: int | None = None
    status: str = "pending"
    priority: int = 5
    notes: str = ""
    # Fields for expanded content types
    poll_options: list[str] | None = None
    poll_duration_hours: int | None = None
    wheel_config_id: int | None = None
    preview_type: str | None = None
    linked_ppv_id: int | None = None
    is_paid_post: bool = False


@dataclass(slots=True)
class ScheduleResult:
    """
    Result of schedule generation.

    Contains the complete output of a schedule generation run,
    including all items, statistics, and validation results.

    Attributes:
        schedule_id: Unique identifier for this schedule.
        creator_id: Creator this schedule is for.
        creator_name: Creator's page name.
        display_name: Creator's display name.
        page_type: Subscription type.
        week_start: Start of schedule week (YYYY-MM-DD).
        week_end: End of schedule week (YYYY-MM-DD).
        volume_level: Volume tier used.
        items: List of scheduled items.
        total_ppvs: Count of PPV items.
        total_bumps: Count of bump items.
        total_follow_ups: Count of follow-up items.
        total_drip: Count of drip items.
        unique_captions: Number of unique captions used.
        avg_freshness: Average freshness score.
        avg_performance: Average performance score.
        validation_passed: Whether validation passed.
        validation_issues: List of validation issues.
        generated_at: Timestamp of generation.
        best_hours: Optimal hours used.
        vault_types: Content types available.
    """

    schedule_id: str
    creator_id: str
    creator_name: str
    display_name: str
    page_type: str
    week_start: str
    week_end: str
    volume_level: str
    items: list[ScheduleItem] = field(default_factory=list)
    total_ppvs: int = 0
    total_bumps: int = 0
    total_follow_ups: int = 0
    total_drip: int = 0
    unique_captions: int = 0
    avg_freshness: float = 0.0
    avg_performance: float = 0.0
    validation_passed: bool = True
    validation_issues: list["ValidationIssue"] = field(default_factory=list)
    generated_at: str = ""
    best_hours: list[int] = field(default_factory=list)
    vault_types: list[str] = field(default_factory=list)
    # Counts for expanded content types
    total_wall_posts: int = 0
    total_free_previews: int = 0
    total_polls: int = 0
    total_game_wheels: int = 0
    # Agent integration tracking
    agents_used: list[str] = field(default_factory=list)
    agents_fallback: list[str] = field(default_factory=list)
    agent_mode: str = "disabled"
    # Fresh selection mode tracking
    selection_mode: str = "legacy"  # "legacy" or "fresh"
    pattern_confidence: float = 0.0
    is_global_fallback: bool = False
    pipeline_context: dict = field(default_factory=dict)


# =============================================================================
# EXTENDED CONTENT TYPE DATACLASSES
# =============================================================================


@dataclass
class WallPostItem:
    """
    Wall/Feed post configuration.

    Represents a wall post that appears on the creator's feed.
    Can be free or paid, and can optionally link to a PPV.

    Attributes:
        post_id: Unique identifier for this wall post.
        caption_id: Foreign key to captions table.
        caption_text: The post caption text.
        content_type_id: Foreign key to content types.
        content_type_name: Human-readable content type.
        is_paid: Whether this is a paid wall post.
        price: Price if paid post.
        linked_ppv_id: Optional linked PPV item ID.
        optimal_hour: Best hour for posting.
        persona_boost: Persona match multiplier.
    """

    post_id: int
    caption_id: int | None
    caption_text: str
    content_type_id: int | None
    content_type_name: str | None
    is_paid: bool = False
    price: float | None = None
    linked_ppv_id: int | None = None
    optimal_hour: int = 18
    persona_boost: float = 1.0


@dataclass
class FreePreview:
    """
    Free preview/teaser content.

    Represents a free preview that teases upcoming paid content.
    Links to a PPV item that will be sent later.

    Attributes:
        preview_id: Unique identifier.
        preview_text: The preview text.
        preview_type: Type of preview (teaser, countdown, etc.).
        content_type_id: Content type being previewed.
        linked_ppv_type: Type of linked PPV content.
        tone: Detected tone for persona matching.
        performance_score: Historical performance.
        freshness_score: Current freshness.
        persona_boost: Persona match multiplier.
    """

    preview_id: int
    preview_text: str
    preview_type: str  # teaser, countdown, behind_scenes, censored
    content_type_id: int | None
    linked_ppv_type: str | None
    tone: str | None
    performance_score: float = 50.0
    freshness_score: float = 100.0
    persona_boost: float = 1.0


@dataclass
class Poll:
    """
    Interactive poll configuration.

    Represents an interactive poll posted to the feed.

    Attributes:
        poll_id: Unique identifier.
        question_text: The poll question.
        options: List of answer options.
        duration_hours: How long poll is open.
        poll_category: Category of poll.
        tone: Detected tone.
        persona_boost: Persona match multiplier.
    """

    poll_id: int
    question_text: str
    options: list[str] = field(default_factory=list)
    duration_hours: int = 24
    poll_category: str = "interactive"
    tone: str | None = None
    persona_boost: float = 1.0


@dataclass
class GameWheelConfig:
    """
    Game wheel configuration.

    Represents a spin-the-wheel game configuration.

    Attributes:
        wheel_id: Unique identifier.
        wheel_name: Display name.
        spin_trigger: What triggers a spin.
        min_trigger_amount: Minimum amount to trigger.
        segments: Wheel segment configurations.
        display_text: Text shown to users.
        cooldown_hours: Hours between spins.
    """

    wheel_id: int
    wheel_name: str
    spin_trigger: str  # tip, ppv_purchase, subscription
    min_trigger_amount: float
    segments: list[dict] = field(default_factory=list)
    display_text: str | None = None
    cooldown_hours: int = 24


@dataclass
class SlotConfig:
    """
    Configuration for a scheduled content slot.

    Slots determine WHEN content is sent. Each slot has a day, time,
    content type, channel, and priority.

    Attributes:
        day: The date for this slot.
        time: The time for this slot.
        content_type: Content type ID.
        channel: Distribution channel.
        slot_priority: Priority 1-5 (1=highest).
        is_follow_up: Whether this is a follow-up.
        parent_slot_id: ID of parent slot if follow-up.
        theme_guidance: Guidance text for slots without captions.
        creator_id: Optional creator ID.
        payday_multiplier: Revenue multiplier.
        is_payday_optimal: True if multiplier >= 1.15.
        is_mid_cycle: True if multiplier <= 0.95.
        slot_id: Optional slot identifier.
    """

    day: date
    time: time
    content_type: str
    channel: str
    slot_priority: int
    is_follow_up: bool = False
    parent_slot_id: str | None = None
    theme_guidance: str | None = None
    creator_id: str | None = None
    payday_multiplier: float = 1.0
    is_payday_optimal: bool = False
    is_mid_cycle: bool = False
    slot_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert slot to dictionary format for compatibility."""
        return {
            "slot_id": self.slot_id,
            "day": self.day.isoformat() if self.day else None,
            "time": self.time.isoformat() if self.time else None,
            "content_type": self.content_type,
            "channel": self.channel,
            "slot_priority": self.slot_priority,
            "is_follow_up": self.is_follow_up,
            "parent_slot_id": self.parent_slot_id,
            "theme_guidance": self.theme_guidance,
            "creator_id": self.creator_id,
            "payday_multiplier": self.payday_multiplier,
            "is_payday_optimal": self.is_payday_optimal,
            "is_mid_cycle": self.is_mid_cycle,
        }


# =============================================================================
# PATTERN-BASED CAPTION SELECTION DATACLASSES
# =============================================================================


@dataclass(frozen=True, slots=True)
class PatternStats:
    """
    Statistics for a specific pattern (content type, tone, hook type, or combination).

    Used to store historical performance data for pattern-based caption scoring.
    Patterns guide selection of fresh/unused captions by predicting their
    likely performance based on similar historically successful content.

    Attributes:
        avg_earnings: Average earnings per use for this pattern (USD).
        sample_count: Number of data points used to calculate statistics.
        normalized_score: Percentile score (0-100) relative to all patterns.
            Higher scores indicate better-performing patterns.

    Example:
        >>> stats = PatternStats(avg_earnings=45.50, sample_count=23, normalized_score=78.5)
        >>> stats.avg_earnings
        45.5
    """

    avg_earnings: float
    sample_count: int
    normalized_score: float  # 0-100 percentile


@dataclass(slots=True)
class PatternProfile:
    """
    Comprehensive pattern profile for a creator or global fallback.

    Contains hierarchical pattern statistics used for scoring fresh captions:
    1. Combined patterns (most specific): "content_type|tone|hook_type"
    2. Individual patterns (fallbacks): content_type, tone, or hook_type alone

    The scoring algorithm tries combined patterns first, falling back to
    individual patterns when combined data is insufficient.

    Attributes:
        creator_id: Unique identifier for the creator, or "global" for fallback.
        combined_patterns: Most specific patterns mapping
            "content_type|tone|hook_type" -> PatternStats.
            Example: "sextape|playful|question" -> PatternStats(...)
        content_type_patterns: Content type only patterns.
            Example: "sextape" -> PatternStats(...)
        tone_patterns: Tone only patterns.
            Example: "playful" -> PatternStats(...)
        hook_patterns: Hook type only patterns.
            Example: "question" -> PatternStats(...)
        sample_count: Total number of historical data points analyzed.
        confidence: Confidence score (0.5-1.0) based on sample size.
            - 0.5: Minimum confidence (few samples, use with caution)
            - 0.75: Moderate confidence (reasonable sample size)
            - 1.0: High confidence (large sample size)
        is_global_fallback: True if this is the global fallback profile
            used when creator-specific data is insufficient.
        cached_at: Timestamp when this profile was generated/cached.

    Example:
        >>> profile = PatternProfile(
        ...     creator_id="creator_123",
        ...     combined_patterns={"sextape|playful|question": PatternStats(45.0, 20, 85.0)},
        ...     content_type_patterns={"sextape": PatternStats(40.0, 100, 70.0)},
        ...     tone_patterns={"playful": PatternStats(38.0, 150, 65.0)},
        ...     hook_patterns={"question": PatternStats(42.0, 80, 72.0)},
        ...     sample_count=500,
        ...     confidence=0.85,
        ...     is_global_fallback=False,
        ...     cached_at=datetime.now()
        ... )
    """

    creator_id: str
    combined_patterns: dict[str, PatternStats] = field(default_factory=dict)
    content_type_patterns: dict[str, PatternStats] = field(default_factory=dict)
    tone_patterns: dict[str, PatternStats] = field(default_factory=dict)
    hook_patterns: dict[str, PatternStats] = field(default_factory=dict)
    sample_count: int = 0
    confidence: float = 0.5
    is_global_fallback: bool = False
    cached_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class ScoredCaption:
    """
    A caption with pattern-based scoring for selection.

    Extends the concept of Caption with additional scoring fields specifically
    designed for the pattern-based selection algorithm. This is the primary
    unit for caption selection, containing all data needed to make weighted
    random selection decisions.

    The selection algorithm prioritizes:
    1. Never-used captions (highest priority)
    2. Fresh captions (freshness >= threshold)
    3. Pattern score (predicted performance based on similar content)

    Attributes:
        caption_id: Unique caption identifier.
        caption_text: The actual caption text content.
        caption_type: Type classification (ppv, follow_up, bump, etc.).
        content_type_id: Foreign key to content_types table.
        content_type_name: Human-readable content type (e.g., "sextape", "solo").
        tone: Detected tone for persona matching (e.g., "playful", "seductive").
        hook_type: Detected hook type (e.g., "question", "urgency", "curiosity").
        freshness_score: Current freshness score (0-100, higher = fresher).
        times_used_on_page: Number of times used on this specific page.
        last_used_date: Date caption was last used (None if never used).
        pattern_score: Predicted performance score (0-100) based on pattern matching.
            Derived from PatternProfile using combined or individual patterns.
        freshness_tier: Classification tier for selection priority:
            - 'never_used': Caption has never been used on this page
            - 'fresh': Freshness score >= threshold (typically 30)
            - 'excluded': Freshness score < threshold (not eligible)
        never_used_on_page: True if this caption has never been used on this page.
            Used for prioritization in selection pools.
        selection_weight: Final computed weight for weighted random selection.
            Combines pattern_score, freshness_tier priority, and persona boost.

    Example:
        >>> caption = ScoredCaption(
        ...     caption_id=12345,
        ...     caption_text="Ready for something special tonight? ...",
        ...     caption_type="ppv",
        ...     content_type_id=3,
        ...     content_type_name="sextape",
        ...     tone="playful",
        ...     hook_type="question",
        ...     freshness_score=85.0,
        ...     times_used_on_page=0,
        ...     last_used_date=None,
        ...     pattern_score=78.5,
        ...     freshness_tier="never_used",
        ...     never_used_on_page=True,
        ...     selection_weight=156.2
        ... )
    """

    caption_id: int
    caption_text: str
    caption_type: str
    content_type_id: int | None
    content_type_name: str | None
    tone: str | None
    hook_type: str | None
    freshness_score: float
    times_used_on_page: int
    last_used_date: date | None
    pattern_score: float
    freshness_tier: str  # 'never_used', 'fresh', 'excluded'
    never_used_on_page: bool
    selection_weight: float


@dataclass(slots=True)
class SelectionPool:
    """
    Pool of scored captions ready for weighted selection.

    Replaces the previous StratifiedPools approach with a unified pool
    that contains pre-scored captions with selection weights. The pool
    tracks metadata about composition for logging and debugging.

    The selection algorithm uses Vose's Alias Method for O(1) weighted
    random selection from the pool.

    Attributes:
        captions: List of ScoredCaption objects ready for selection.
            Pre-filtered to exclude captions below freshness threshold.
        never_used_count: Count of captions with freshness_tier='never_used'.
            Used for monitoring pool health and diversity.
        fresh_count: Count of captions with freshness_tier='fresh'.
            These are reusable captions above the freshness threshold.
        total_weight: Sum of all selection_weight values in the pool.
            Used for normalizing probabilities in selection.
        creator_id: Creator this pool was built for.
        content_types: List of content types represented in the pool.
            Useful for debugging content type coverage.

    Example:
        >>> pool = SelectionPool(
        ...     captions=[scored_caption_1, scored_caption_2, ...],
        ...     never_used_count=45,
        ...     fresh_count=120,
        ...     total_weight=8750.5,
        ...     creator_id="creator_123",
        ...     content_types=["sextape", "solo", "b/g"]
        ... )
        >>> pool.never_used_count / len(pool.captions)  # % never used
        0.273

    Note:
        The pool should be rebuilt when:
        - Caption freshness scores are updated
        - New captions are added to the database
        - Creator's pattern profile is updated
    """

    captions: list[ScoredCaption] = field(default_factory=list)
    never_used_count: int = 0
    fresh_count: int = 0
    total_weight: float = 0.0
    creator_id: str = ""
    content_types: list[str] = field(default_factory=list)


# =============================================================================
# VALIDATION DATACLASSES
# =============================================================================


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """
    Represents a validation issue with optional auto-correction capability.

    Attributes:
        rule_name: The name of the validation rule that was violated.
        severity: The severity level - "error", "warning", or "info".
        message: Human-readable description of the issue.
        item_ids: Tuple of schedule item IDs affected by this issue.
        auto_correctable: Whether this issue can be automatically corrected.
        correction_action: The type of correction to apply.
        correction_value: The value to apply for correction (JSON or string).
    """

    rule_name: str
    severity: str  # error, warning, info
    message: str
    item_ids: tuple[int, ...] = ()
    # Auto-correction fields
    auto_correctable: bool = False
    correction_action: str = ""  # "move_slot", "swap_caption", "adjust_timing"
    correction_value: str = ""  # New value to apply (JSON or string)


@dataclass(slots=True)
class ValidationResult:
    """
    Result of validation.

    Contains all validation issues found during schedule validation.

    Attributes:
        is_valid: True if no errors were found.
        error_count: Number of error-level issues.
        warning_count: Number of warning-level issues.
        info_count: Number of info-level issues.
        issues: List of all validation issues.
    """

    is_valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ) -> None:
        """Add an error issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="error",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
        self.error_count += 1
        self.is_valid = False

    def add_warning(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ) -> None:
        """Add a warning issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="warning",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
        self.warning_count += 1

    def add_info(
        self,
        rule: str,
        message: str,
        item_ids: list[int] | None = None,
        auto_correctable: bool = False,
        correction_action: str = "",
        correction_value: str = "",
    ) -> None:
        """Add an info issue with optional auto-correction data."""
        self.issues.append(
            ValidationIssue(
                rule_name=rule,
                severity="info",
                message=message,
                item_ids=tuple(item_ids) if item_ids else (),
                auto_correctable=auto_correctable,
                correction_action=correction_action,
                correction_value=correction_value,
            )
        )
        self.info_count += 1


# =============================================================================
# AGENT/PIPELINE DATACLASSES
# =============================================================================


@dataclass(frozen=False)
class AgentRequest:
    """
    Request for Claude to invoke a sub-agent.

    This is output by Python when running in HYBRID mode, signaling that
    Claude should invoke the specified agent via Task tool.

    Attributes:
        request_id: Unique ID for matching response.
        agent_name: Agent file name in ~/.claude/agents/eros-scheduling/.
        agent_model: Model to use (haiku, sonnet, opus).
        timeout_seconds: Timeout for agent execution.
        context: Input data for agent.
        expected_output_schema: Name of expected output type.
        cache_key: Optional key for caching (None = don't cache).
    """

    request_id: str
    agent_name: str
    agent_model: str
    timeout_seconds: int
    context: dict[str, Any]
    expected_output_schema: str
    cache_key: str | None = None


@dataclass(frozen=False)
class AgentResponse:
    """
    Response from a sub-agent invocation.

    Written by Claude after invoking an agent, read by Python on resume.

    Attributes:
        request_id: Matches the request_id from AgentRequest.
        agent_name: Name of the agent that was invoked.
        success: Whether the agent succeeded.
        result: Agent output parsed as dict.
        error: Error message if success=False.
        fallback_used: True if fallback was used instead of agent.
        execution_time_ms: Execution time in milliseconds.
        cached: True if result was from cache.
    """

    request_id: str
    agent_name: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    fallback_used: bool = False
    execution_time_ms: int = 0
    cached: bool = False


@dataclass(frozen=False)
class PipelineState:
    """
    State for pipeline pause/resume in hybrid mode.

    Saved to disk when pipeline pauses for agent invocation,
    loaded on resume to continue from where we left off.

    Attributes:
        session_id: Unique session identifier.
        creator_id: Creator being processed.
        week: Week string (YYYY-Www).
        mode: Pipeline mode.
        current_step: Current step number.
        completed_steps: List of completed step numbers.
        pending_agent_requests: Pending agent request dicts.
        received_agent_responses: Received agent response dicts.
        partial_schedule_items: Partially built schedule items.
        context_snapshot: Snapshot of context at pause.
    """

    session_id: str
    creator_id: str
    week: str
    mode: str  # "hybrid"
    current_step: str
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


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    """
    Canonical persona profile - single source of truth.

    All modules MUST import from models, not define their own.

    Attributes:
        creator_id: Unique creator identifier.
        page_name: Creator's page name.
        primary_tone: Primary voice tone.
        secondary_tone: Optional secondary tone.
        emoji_frequency: Emoji usage level.
        favorite_emojis: Tuple of preferred emojis.
        slang_level: Slang usage level.
        avg_sentiment: Average sentiment score (0.0-1.0).
        avg_caption_length: Average caption character length.
    """

    creator_id: str
    page_name: str
    primary_tone: str
    secondary_tone: str | None = None
    emoji_frequency: str = "moderate"
    favorite_emojis: tuple[str, ...] = ()
    slang_level: str = "light"
    avg_sentiment: float = 0.5
    avg_caption_length: int = 100


@dataclass(frozen=False)
class PricingStrategy:
    """Output from pricing-strategist agent."""

    content_type_prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    page_type_modifier: float = 1.0
    weekly_revenue_projection: float = 0.0
    generated_at: str = ""


@dataclass(frozen=False)
class TimingStrategy:
    """Output from timezone-optimizer agent."""

    timezone: str = "America/New_York"
    peak_windows: list[dict[str, Any]] = field(default_factory=list)
    avoid_windows: list[dict[str, Any]] = field(default_factory=list)
    best_days: list[str] = field(default_factory=list)
    daily_schedule: dict[str, list[str]] = field(default_factory=dict)
    generated_at: str = ""


@dataclass(frozen=False)
class RotationStrategy:
    """Output from content-rotation-architect agent."""

    persona_type: str = ""
    weekly_rotation: list[dict[str, Any]] = field(default_factory=list)
    spacing_rules: dict[str, Any] = field(default_factory=dict)
    vault_warnings: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class FollowUpSequence:
    """Output from multi-touch-sequencer agent for a single PPV."""

    ppv_item_id: int = 0
    sequence: list[dict[str, Any]] = field(default_factory=list)
    abort_triggers: list[str] = field(default_factory=list)


@dataclass(frozen=False)
class RevenueProjection:
    """Output from revenue-forecaster agent."""

    schedule_week: str = ""
    projections: dict[str, dict[str, Any]] = field(default_factory=dict)
    drivers: dict[str, float] = field(default_factory=dict)
    risk_factors: list[str] = field(default_factory=list)
    opportunity_flags: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class PageTypeRules:
    """Output from page-type-optimizer agent."""

    page_type: str = ""
    rules_applied: dict[str, Any] = field(default_factory=dict)
    adjustments_made: list[str] = field(default_factory=list)
    generated_at: str = ""


@dataclass(frozen=False)
class ScheduleContext:
    """
    Master context object passed between all agents during schedule generation.

    This accumulates data from each agent in the pipeline, allowing downstream
    agents to leverage insights from upstream agents.

    Attributes:
        creator_id: Unique creator identifier.
        week_start: Start date of the scheduling week.
        week_end: End date of the scheduling week.
        creator_profile: Loaded creator profile data.
        persona_profile: Loaded persona profile.
        pricing: Pricing strategy from agent.
        timing: Timing strategy from agent.
        rotation: Rotation strategy from agent.
        followup_sequences: Generated follow-up sequences.
        revenue_projection: Revenue projection from agent.
        page_type_rules: Page type rules from agent.
        validation_result: Validation result from agent.
        mode: Pipeline mode ("quick" or "full").
        agents_used: List of agents successfully used.
        fallbacks_used: List of agents that fell back.
    """

    creator_id: str
    week_start: date
    week_end: date

    # Input data from database
    creator_profile: "CreatorProfile | None" = None
    persona_profile: PersonaProfile | None = None

    # Agent outputs (accumulated during pipeline)
    pricing: PricingStrategy | None = None
    timing: TimingStrategy | None = None
    rotation: RotationStrategy | None = None
    followup_sequences: list[FollowUpSequence] = field(default_factory=list)
    revenue_projection: RevenueProjection | None = None
    page_type_rules: PageTypeRules | None = None
    validation_result: "ValidationResult | None" = None

    # Pipeline metadata
    mode: str = "quick"
    agents_used: list[str] = field(default_factory=list)
    fallbacks_used: list[str] = field(default_factory=list)
    execution_start: str = ""
    execution_end: str = ""

    # Payday context
    high_value_days: list[date] = field(default_factory=list)
    flash_sale_day: date | None = None
    payday_multipliers: dict[str, float] = field(default_factory=dict)

    # Timing confidence metrics
    best_hours_confidence: float = 0.0
    fallback_hours_used: bool = False

    # Inventory signals
    low_caption_inventory: bool = False
    content_types_exhausted: list[str] = field(default_factory=list)

    # Hook tracking
    hooks_used_this_week: list[str] = field(default_factory=list)

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
            "high_value_days": [d.isoformat() for d in self.high_value_days],
            "flash_sale_day": self.flash_sale_day.isoformat() if self.flash_sale_day else None,
            "payday_multipliers": self.payday_multipliers,
            "best_hours_confidence": self.best_hours_confidence,
            "fallback_hours_used": self.fallback_hours_used,
            "low_caption_inventory": self.low_caption_inventory,
            "content_types_exhausted": self.content_types_exhausted,
            "hooks_used_this_week": self.hooks_used_this_week,
        }

    def mark_agent_used(self, agent_name: str) -> None:
        """Record that an agent was successfully invoked."""
        if agent_name not in self.agents_used:
            self.agents_used.append(agent_name)

    def mark_fallback_used(self, agent_name: str) -> None:
        """Record that a fallback was used instead of an agent."""
        if agent_name not in self.fallbacks_used:
            self.fallbacks_used.append(agent_name)


# =============================================================================
# PYDANTIC MODELS - API Boundaries
# =============================================================================

try:
    from pydantic import BaseModel, Field, field_validator

    PYDANTIC_AVAILABLE = True

    class ScheduleRequest(BaseModel):
        """
        Input validation for schedule generation requests.

        This Pydantic model validates API-level input before passing
        to the schedule generation pipeline.

        Attributes:
            creator_name: Name of the creator (page_name).
            week: ISO week string (YYYY-Www format).
            mode: Pipeline mode ("quick" or "full").
            output_format: Output format ("json", "markdown", "csv").
            volume_level: Optional volume level override.
            enable_follow_ups: Whether to enable follow-ups.
            enable_wall_posts: Whether to enable wall posts.
            enable_polls: Whether to enable polls.
        """

        creator_name: str = Field(..., min_length=1, description="Creator page name")
        week: str = Field(
            ...,
            pattern=r"^\d{4}-W\d{2}$",
            description="ISO week string (YYYY-Www)",
        )
        mode: str = Field(
            default="full",
            pattern=r"^(quick|full)$",
            description="Pipeline mode",
        )
        output_format: str = Field(
            default="json",
            pattern=r"^(json|markdown|csv)$",
            description="Output format",
        )
        volume_level: str | None = Field(
            default=None,
            description="Volume level override (Base, Low, Mid, High, Ultra)",
        )
        enable_follow_ups: bool = Field(
            default=True,
            description="Enable follow-up message generation",
        )
        enable_wall_posts: bool = Field(
            default=False,
            description="Enable wall post generation",
        )
        enable_polls: bool = Field(
            default=False,
            description="Enable poll generation",
        )

        @field_validator("volume_level")
        @classmethod
        def validate_volume_level(cls, v: str | None) -> str | None:
            """Validate volume level if provided."""
            if v is not None:
                valid_levels = {"Base", "Low", "Mid", "Growth", "Scale", "High", "Ultra"}
                if v not in valid_levels:
                    raise ValueError(f"volume_level must be one of {valid_levels}")
            return v

    class ScheduleItemResponse(BaseModel):
        """Pydantic model for a single schedule item in response."""

        item_id: int
        creator_id: str
        scheduled_date: str
        scheduled_time: str
        item_type: str
        channel: str = "mass_message"
        caption_id: int | None = None
        caption_text: str | None = None
        content_type_id: int | None = None
        content_type_name: str | None = None
        suggested_price: float | None = None
        freshness_score: float = 100.0
        performance_score: float = 50.0
        is_follow_up: bool = False
        parent_item_id: int | None = None
        status: str = "pending"
        priority: int = 5

    class ValidationIssueResponse(BaseModel):
        """Pydantic model for validation issue in response."""

        rule_name: str
        severity: str
        message: str
        item_ids: list[int] = []
        auto_correctable: bool = False
        correction_action: str = ""
        correction_value: str = ""

    class ScheduleResponse(BaseModel):
        """
        Output validation for schedule generation.

        This Pydantic model ensures consistent API output format.

        Attributes:
            schedule_id: Unique schedule identifier.
            creator: Creator page name.
            week: ISO week string.
            mode: Pipeline mode used.
            items: List of schedule items.
            validation: Validation results.
            metadata: Additional metadata.
        """

        schedule_id: str = Field(..., description="Unique schedule identifier")
        creator: str = Field(..., description="Creator page name")
        week: str = Field(..., description="ISO week string")
        mode: str = Field(..., description="Pipeline mode used")
        items: list[ScheduleItemResponse] = Field(
            default_factory=list,
            description="List of schedule items",
        )
        validation: dict[str, Any] = Field(
            default_factory=dict,
            description="Validation results",
        )
        metadata: dict[str, Any] = Field(
            default_factory=dict,
            description="Additional metadata",
        )

        @classmethod
        def from_schedule_result(cls, result: ScheduleResult) -> "ScheduleResponse":
            """Create response from ScheduleResult dataclass."""
            return cls(
                schedule_id=result.schedule_id,
                creator=result.creator_name,
                week=result.week_start,
                mode="full",  # Default, should be passed in
                items=[
                    ScheduleItemResponse(
                        item_id=item.item_id,
                        creator_id=item.creator_id,
                        scheduled_date=item.scheduled_date,
                        scheduled_time=item.scheduled_time,
                        item_type=item.item_type,
                        channel=item.channel,
                        caption_id=item.caption_id,
                        caption_text=item.caption_text,
                        content_type_id=item.content_type_id,
                        content_type_name=item.content_type_name,
                        suggested_price=item.suggested_price,
                        freshness_score=item.freshness_score,
                        performance_score=item.performance_score,
                        is_follow_up=item.is_follow_up,
                        parent_item_id=item.parent_item_id,
                        status=item.status,
                        priority=item.priority,
                    )
                    for item in result.items
                ],
                validation={
                    "passed": result.validation_passed,
                    "issues": [
                        {
                            "rule_name": issue.rule_name,
                            "severity": issue.severity,
                            "message": issue.message,
                            "item_ids": list(issue.item_ids),
                        }
                        for issue in result.validation_issues
                    ],
                },
                metadata={
                    "generated_at": result.generated_at,
                    "total_ppvs": result.total_ppvs,
                    "total_bumps": result.total_bumps,
                    "total_follow_ups": result.total_follow_ups,
                    "unique_captions": result.unique_captions,
                    "avg_freshness": result.avg_freshness,
                    "avg_performance": result.avg_performance,
                },
            )

except ImportError:
    PYDANTIC_AVAILABLE = False
    # Provide stub classes for when Pydantic is not available
    ScheduleRequest = None  # type: ignore
    ScheduleResponse = None  # type: ignore
    ScheduleItemResponse = None  # type: ignore
    ValidationIssueResponse = None  # type: ignore


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "SlotType",
    "ContentChannel",
    "PageType",
    "VolumeLevel",
    "Severity",
    "AgentInvokerMode",
    # Core Dataclasses
    "ScheduleConfig",
    "CreatorProfile",
    "Caption",
    "ScheduleItem",
    "ScheduleResult",
    # Extended Content Types
    "WallPostItem",
    "FreePreview",
    "Poll",
    "GameWheelConfig",
    "SlotConfig",
    # Pattern-Based Caption Selection
    "PatternStats",
    "PatternProfile",
    "ScoredCaption",
    "SelectionPool",
    # Validation
    "ValidationIssue",
    "ValidationResult",
    # Agent/Pipeline
    "AgentRequest",
    "AgentResponse",
    "PipelineState",
    "PersonaProfile",
    "PricingStrategy",
    "TimingStrategy",
    "RotationStrategy",
    "FollowUpSequence",
    "RevenueProjection",
    "PageTypeRules",
    "ScheduleContext",
    # Pydantic Models (API Boundaries)
    "ScheduleRequest",
    "ScheduleResponse",
    "ScheduleItemResponse",
    "ValidationIssueResponse",
    "PYDANTIC_AVAILABLE",
]
