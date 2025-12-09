#!/usr/bin/env python3
"""
Generate Schedule - Main entry point for EROS schedule generation.

This script implements the 9-step schedule generation pipeline for
creating optimized weekly content schedules for OnlyFans creators.

Usage:
    python generate_schedule.py --creator missalexa --week 2025-W01
    python generate_schedule.py --creator-id abc123 --week 2025-W01 --output schedule.md
    python generate_schedule.py --batch --week 2025-W01 --format json

Pipeline Steps:
    1. ANALYZE - Load creator profile and analytics
    2. MATCH CONTENT - Filter by vault availability
    3. MATCH PERSONA - Score by voice profile
    4. BUILD STRUCTURE - Create weekly time slots
    5. ASSIGN CAPTIONS - Weighted selection (Vose Alias)
    6. GENERATE FOLLOW-UPS - Create follow-ups (if enabled)
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones (if enabled)
    8. APPLY PAGE TYPE RULES - Paid vs Free rules (if enabled)
    9. VALIDATE & RETURN - Check business rules

Critical Business Rules:
    - PPV Spacing: MINIMUM 3 hours between PPV messages
    - Follow-ups: 15-45 minutes after each PPV (randomized)
    - Drip Windows: 4-8 hours, NO buying opportunities during window
    - Freshness: ALL captions must have freshness >= 30
    - Rotation: NEVER same content type consecutively
    - Vault: ALL content types must exist in creator's vault
"""

import argparse
import json
import logging
import os
import random
import re
import sqlite3
import sys
import uuid

# Configure module logger
logger = logging.getLogger(__name__)
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from utils import VoseAliasSelector
from volume_optimizer import MultiFactorVolumeOptimizer, VolumeStrategy
from weights import (
    calculate_weight,
    determine_pool_type,
    get_max_earnings,
    POOL_PROVEN,
    POOL_GLOBAL_EARNER,
    POOL_DISCOVERY,
)
from content_type_strategy import (
    ContentTypeStrategy,
    get_content_type_earnings,
    allocate_slots_weighted,
    PREMIUM_HOURS,
)

# Stratified pools dataclass for pool-based selection
from dataclasses import dataclass as _dataclass


@_dataclass
class StratifiedPools:
    """
    Stratified caption pools for a single content type.

    Pools:
        - proven: Captions with creator-specific earnings data
        - global_earner: Captions with global earnings but no creator data
        - discovery: Captions with no earnings data
    """
    content_type_id: int
    content_type_name: str
    proven: list  # List[Caption]
    global_earner: list  # List[Caption]
    discovery: list  # List[Caption]
    content_type_avg_earnings: float = 50.0

    @property
    def total_count(self) -> int:
        """Total captions across all pools."""
        return len(self.proven) + len(self.global_earner) + len(self.discovery)

    @property
    def has_proven(self) -> bool:
        """Whether this content type has proven performers."""
        return len(self.proven) > 0

# New pipeline modules for full mode
try:
    from quality_scoring import QualityScorer, calculate_enhanced_weight, get_quality_modifier
    QUALITY_SCORING_AVAILABLE = True
except ImportError:
    QUALITY_SCORING_AVAILABLE = False

try:
    from caption_enhancer import CaptionEnhancer, EnhancementResult, PersonaContext as CEPersonaContext
    CAPTION_ENHANCER_AVAILABLE = True
except ImportError:
    CAPTION_ENHANCER_AVAILABLE = False

try:
    from followup_generator import FollowupGenerator, FollowUpContext, FollowUpMessage
    FOLLOWUP_GENERATOR_AVAILABLE = True
except ImportError:
    FOLLOWUP_GENERATOR_AVAILABLE = False

# Agent invoker for sub-agent integration
try:
    from agent_invoker import AgentInvoker, AGENT_CONFIGS
    from shared_context import (
        ScheduleContext,
        CreatorProfile as AgentCreatorProfile,
        PersonaProfile,
    )
    AGENT_INVOKER_AVAILABLE = True
except ImportError:
    AGENT_INVOKER_AVAILABLE = False

# Content type loaders for new content types
try:
    from content_type_loaders import (
        load_wall_post_captions,
        load_free_previews,
        load_polls,
        load_game_wheel_config,
        apply_preview_persona_scores,
        apply_poll_persona_scores,
    )
    CONTENT_TYPE_LOADERS_AVAILABLE = True
except ImportError:
    CONTENT_TYPE_LOADERS_AVAILABLE = False

# Content type schedulers for new content types
try:
    from content_type_schedulers import (
        select_wall_posts_for_slots,
        select_previews_for_ppvs,
        select_polls_for_week,
        create_game_wheel_schedule_item,
        generate_wall_post_slots,
        generate_poll_slots,
    )
    CONTENT_TYPE_SCHEDULERS_AVAILABLE = True
except ImportError:
    CONTENT_TYPE_SCHEDULERS_AVAILABLE = False


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

__all__ = [
    # Exceptions
    "ErosScheduleError",
    "CreatorNotFoundError",
    "CaptionExhaustionError",
    "VaultEmptyError",
    # Core classes
    "ScheduleConfig",
    "CreatorProfile",
    "Caption",
    "ScheduleItem",
    "ValidationIssue",
    "ScheduleResult",
    # Extended content type classes
    "WallPostItem",
    "FreePreview",
    "Poll",
    "GameWheelConfig",
    # Main functions
    "generate_schedule",
    "generate_batch_schedules",
    "load_creator_profile",
    "format_markdown",
    "format_json",
]


def parse_content_notes(notes_json: str | None) -> dict:
    """Parse JSON notes from creators.notes field."""
    if not notes_json:
        return {}
    try:
        return json.loads(notes_json)
    except json.JSONDecodeError:
        return {"page_strategy": notes_json}  # Legacy plain text


def extract_filter_keywords(notes: dict) -> set[str]:
    """Extract all keywords to filter from content notes."""
    keywords = set()
    # From caption_filters
    if notes.get("caption_filters", {}).get("exclude_keywords"):
        keywords.update(notes["caption_filters"]["exclude_keywords"])
    # From content_restrictions
    for restriction in notes.get("content_restrictions", []):
        if restriction.get("filter_keywords"):
            keywords.update(restriction["filter_keywords"])
    return keywords


def extract_price_modifiers(notes: dict) -> dict[str | None, float]:
    """Extract price modifiers by content type."""
    modifiers = {}
    # From pricing_guidance
    for guidance in notes.get("pricing_guidance", []):
        content_type = guidance.get("content_type")  # None = all content
        modifier = guidance.get("price_modifier", 1.0)
        modifiers[content_type] = modifier
    # From content_restrictions (some have price modifiers)
    for restriction in notes.get("content_restrictions", []):
        if restriction.get("price_modifier"):
            content_type = restriction.get("content_type")
            modifiers[content_type] = restriction["price_modifier"]
    return modifiers


class ErosScheduleError(Exception):
    """Base exception for EROS schedule generation errors."""
    pass


class CreatorNotFoundError(ErosScheduleError):
    """Raised when creator cannot be found in database."""

    def __init__(self, identifier: str):
        super().__init__(f"Creator not found: {identifier}")
        self.identifier = identifier


class CaptionExhaustionError(ErosScheduleError):
    """Raised when no captions meet freshness threshold."""

    def __init__(self, creator_id: str, min_freshness: float):
        super().__init__(f"No captions with freshness >= {min_freshness} for {creator_id}")
        self.creator_id = creator_id
        self.min_freshness = min_freshness


class VaultEmptyError(ErosScheduleError):
    """Raised when creator's vault has no content."""

    def __init__(self, creator_id: str, creator_name: str | None = None):
        name_info = f" ('{creator_name}')" if creator_name else ""
        super().__init__(
            f"Creator{name_info} has no content types in vault. "
            f"Cannot generate schedule. Update vault_matrix table for creator_id={creator_id}."
        )
        self.creator_id = creator_id
        self.creator_name = creator_name


# Path resolution for database and SQL files
SCRIPT_DIR = Path(__file__).parent
SQL_DIR = SCRIPT_DIR.parent / "assets" / "sql"

# Database path resolution with multiple candidate locations
# Standard order: 1) env var, 2) Developer, 3) Documents, 4) .eros fallback
HOME_DIR = Path.home()

# Build candidates list with env var first (if set)
_env_db_path = os.environ.get("EROS_DATABASE_PATH", "")
DB_PATH_CANDIDATES = [
    Path(_env_db_path) if _env_db_path else None,  # Environment variable (highest priority)
    HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / "Documents" / "EROS-SD-MAIN-PROJECT" / "database" / "eros_sd_main.db",
    HOME_DIR / ".eros" / "eros.db",
]
# Filter out None entries
DB_PATH_CANDIDATES = [p for p in DB_PATH_CANDIDATES if p is not None]

DB_PATH = next((p for p in DB_PATH_CANDIDATES if p.exists()), DB_PATH_CANDIDATES[1] if len(DB_PATH_CANDIDATES) > 1 else DB_PATH_CANDIDATES[0])

# Default output directory for schedules
# Priority: 1) EROS_SCHEDULES_PATH env var, 2) Developer project path
_env_schedules_path = os.environ.get("EROS_SCHEDULES_PATH", "")
DEFAULT_SCHEDULES_DIR = (
    Path(_env_schedules_path) if _env_schedules_path
    else HOME_DIR / "Developer" / "EROS-SD-MAIN-PROJECT" / "schedules"
)

# Business rule constants
MIN_PPV_SPACING_HOURS = 3  # Critical: minimum 3 hours between PPVs
RECOMMENDED_PPV_SPACING_HOURS = 4  # Recommended: 4 hours between PPVs
MIN_FRESHNESS_SCORE = 30  # Minimum freshness score for all captions
FOLLOW_UP_MIN_MINUTES = 15  # Minimum time after PPV for follow-up
FOLLOW_UP_MAX_MINUTES = 45  # Maximum time after PPV for follow-up
DRIP_WINDOW_START_HOUR = 14  # Drip window starts at 2 PM
DRIP_WINDOW_END_HOUR = 22  # Drip window ends at 10 PM

# Content type rotation order (preferred sequence)
ROTATION_ORDER = ["solo", "bundle", "winner", "sextape", "bg", "gg", "toy_play", "custom", "dick_rate"]

# Follow-up bump messages
BUMP_MESSAGES = [
    "Have you seen this yet?",
    "Don't miss out on this one!",
    "Still available for you...",
    "Limited time offer!",
    "Just checking if you caught this?",
    "This won't last forever...",
    "Thought you'd want to see this",
    "Special content waiting for you",
]


def format_week_string(week_start: date) -> str:
    """Format date as ISO week string (YYYY-Www)."""
    iso_year, iso_week, _ = week_start.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


@dataclass(frozen=True, slots=True)
class ScheduleConfig:
    """Configuration for schedule generation."""

    creator_id: str
    creator_name: str
    page_type: str  # paid or free
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
    volume_period: str = "day"          # "day" or "week"
    ppv_per_week: int = 0               # Weekly total for tracking
    is_paid_page: bool = False          # Convenience flag
    volume_strategy: Optional[VolumeStrategy] = None  # Full strategy object
    # Enhanced pipeline mode fields (Phase 4 integration)
    mode: str = "quick"                 # "quick" or "full" - pipeline mode
    use_quality_scoring: bool = False   # Enable LLM quality scoring (full mode)
    use_caption_enhancement: bool = False  # Enable caption enhancement (full mode)
    use_context_followups: bool = False # Enable context-aware follow-ups (full mode)
    # Sub-agent integration
    use_agents: bool = False            # Enable sub-agent delegation for enhanced optimization
    # Content type toggles (Phase 2 expansion)
    enable_wall_posts: bool = False
    wall_posts_per_day: int = 2
    enable_free_previews: bool = False
    previews_per_day: int = 1
    enable_polls: bool = False
    polls_per_week: int = 3
    enable_game_wheel: bool = False
    wall_post_hours: tuple[int, ...] = (12, 16, 20)  # Use tuple instead of list for frozen dataclass
    preview_lead_time_hours: int = 2
    # NEW: Earnings-based selection config
    earnings_weight: float = 0.70          # Primary factor (~70%)
    earnings_freshness_weight: float = 0.20  # Secondary factor (~20%)
    persona_tiebreak_weight: float = 0.10  # Tiebreaker (~10%)
    reserved_slot_ratio: float = 0.15      # 15% of slots for untested
    min_uses_for_tested: int = 3           # Threshold for "tested" status


@dataclass(slots=True)
class CreatorProfile:
    """Creator profile data from database."""

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


@dataclass
class Caption:
    """Caption data for selection."""

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
    # NEW: Earnings-based fields for priority selection
    creator_avg_earnings: float | None = None  # Creator-specific avg earnings
    global_avg_earnings: float | None = None   # Global avg earnings (fallback)
    creator_times_used: int = 0                # Times used by THIS creator
    global_times_used: int = 0                 # Global times used
    earnings_source: str = "none"              # "creator", "global", or "none"
    is_untested: bool = False                  # True if <3 uses for this creator


@dataclass
class WallPostItem:
    """Wall/Feed post configuration."""
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
    """Free preview/teaser content."""
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
    """Interactive poll configuration."""
    poll_id: int
    question_text: str
    options: list[str] = field(default_factory=list)
    duration_hours: int = 24
    poll_category: str = "interactive"
    tone: str | None = None
    persona_boost: float = 1.0


@dataclass
class GameWheelConfig:
    """Game wheel configuration."""
    wheel_id: int
    wheel_name: str
    spin_trigger: str  # tip, ppv_purchase, subscription
    min_trigger_amount: float
    segments: list[dict] = field(default_factory=list)  # [{name, probability, prize_type, prize_value}]
    display_text: str | None = None
    cooldown_hours: int = 24


@dataclass
class ScheduleItem:
    """Represents a scheduled content item."""

    item_id: int
    creator_id: str
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str  # HH:MM
    item_type: str  # ppv, bump, wall_post, drip, free_preview, poll, game_wheel
    channel: str = "mass_message"  # mass_message, campaign, direct_unlock, feed, poll, gamification
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
    poll_options: list[str] | None = None  # For polls
    poll_duration_hours: int | None = None  # For polls
    wheel_config_id: int | None = None  # For game wheel
    preview_type: str | None = None  # For free previews
    linked_ppv_id: int | None = None  # For wall posts and previews
    is_paid_post: bool = False  # For paid wall posts


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Represents a validation issue."""

    rule_name: str
    severity: str  # error, warning, info
    message: str
    item_ids: tuple[int, ...] = ()


@dataclass
class ScheduleResult:
    """Result of schedule generation."""

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
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    generated_at: str = ""
    best_hours: list[int] = field(default_factory=list)
    vault_types: list[str] = field(default_factory=list)
    # Counts for expanded content types (Phase 2 expansion)
    total_wall_posts: int = 0
    total_free_previews: int = 0
    total_polls: int = 0
    total_game_wheels: int = 0
    # Agent integration tracking (Phase 3)
    agents_used: list[str] = field(default_factory=list)
    agents_fallback: list[str] = field(default_factory=list)
    agent_mode: str = "disabled"  # "disabled", "enabled", "partial"


def get_db_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get database connection with row factory."""
    path = db_path or DB_PATH
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_volume_level(
    active_fans: int,
    conn: sqlite3.Connection = None,
    creator_id: str = None
) -> tuple[str, int, int]:
    """
    Multi-factor volume determination.

    Returns:
        (level_name, ppv_per_period, bumps_per_ppv)

    Note: ppv_per_period is WEEKLY for paid pages, DAILY for free pages.
    Check the VolumeStrategy.volume_period to determine interpretation.
    """
    if conn and creator_id:
        optimizer = MultiFactorVolumeOptimizer(conn)
        strategy = optimizer.calculate_optimal_volume(creator_id, active_fans)
        return (strategy.volume_level, strategy.ppv_per_day, strategy.bump_per_day)

    # Fallback for backward compatibility (assumes free page daily)
    if active_fans < 1000:
        return ("Low", 2, 2)
    elif active_fans < 5000:
        return ("Mid", 3, 2)
    elif active_fans < 15000:
        return ("High", 4, 2)
    else:
        return ("Ultra", 5, 2)


def parse_iso_week(week_str: str) -> tuple[date, date]:
    """
    Parse ISO week string to start and end dates.

    Args:
        week_str: Week in format YYYY-Www (e.g., 2025-W01)

    Returns:
        Tuple of (monday, sunday) dates
    """
    year, week = week_str.split("-W")
    year = int(year)
    week = int(week)

    jan1 = date(year, 1, 1)
    jan1_weekday = jan1.weekday()

    if jan1_weekday <= 3:
        week1_monday = jan1 - timedelta(days=jan1_weekday)
    else:
        week1_monday = jan1 + timedelta(days=7 - jan1_weekday)

    monday = week1_monday + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)

    return monday, sunday


# ============================================================================
# STEP 1: ANALYZE - Load creator profile and analytics
# ============================================================================

def load_creator_profile(
    conn: sqlite3.Connection,
    creator_name: str | None = None,
    creator_id: str | None = None
) -> CreatorProfile | None:
    """
    Load creator profile from database.

    Step 1 of pipeline: ANALYZE
    """
    if not creator_name and not creator_id:
        raise ValueError("Must provide either creator_name or creator_id")

    if creator_name:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans, c.notes,
                   cp.primary_tone, cp.emoji_frequency, cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.page_name = ? OR c.display_name = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_name, creator_name))
    else:
        query = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.current_active_fans, c.notes,
                   cp.primary_tone, cp.emoji_frequency, cp.slang_level, cp.avg_sentiment
            FROM creators c
            LEFT JOIN creator_personas cp ON c.creator_id = cp.creator_id
            WHERE c.creator_id = ?
            LIMIT 1
        """
        cursor = conn.execute(query, (creator_id,))

    row = cursor.fetchone()
    if not row:
        return None

    active_fans = row["current_active_fans"] or 0
    volume_level, _, _ = get_volume_level(active_fans)

    # Load best hours from historical data
    best_hours = load_optimal_hours(conn, row["creator_id"])

    # Load vault content types
    vault_types = load_vault_types(conn, row["creator_id"])

    # Validate vault is not empty - critical for schedule generation
    if not vault_types:
        raise VaultEmptyError(row["creator_id"], row["page_name"])

    # Parse content notes and extract filter keywords/price modifiers
    content_notes = parse_content_notes(row["notes"] if row["notes"] else None)
    filter_keywords = extract_filter_keywords(content_notes)
    price_modifiers = extract_price_modifiers(content_notes)

    return CreatorProfile(
        creator_id=row["creator_id"],
        page_name=row["page_name"],
        display_name=row["display_name"] or row["page_name"],
        page_type=row["page_type"] or "paid",
        active_fans=active_fans,
        volume_level=volume_level,
        primary_tone=row["primary_tone"] or "playful",
        emoji_frequency=row["emoji_frequency"] or "moderate",
        slang_level=row["slang_level"] or "light",
        avg_sentiment=row["avg_sentiment"] or 0.5,
        best_hours=best_hours,
        vault_types=vault_types,
        content_notes=content_notes,
        filter_keywords=filter_keywords,
        price_modifiers=price_modifiers
    )


def load_optimal_hours(conn: sqlite3.Connection, creator_id: str) -> list[int]:
    """Load best performing hours from historical data."""
    query = """
        SELECT sending_hour, AVG(earnings) as avg_earnings
        FROM mass_messages
        WHERE creator_id = ?
          AND message_type = 'ppv'
          AND earnings IS NOT NULL
          AND sending_time >= datetime('now', '-90 days')
        GROUP BY sending_hour
        HAVING COUNT(*) >= 3
        ORDER BY avg_earnings DESC
        LIMIT 10
    """
    cursor = conn.execute(query, (creator_id,))
    hours = [row["sending_hour"] for row in cursor.fetchall()]

    # Fall back to default peak hours if no data
    if not hours:
        hours = [10, 14, 18, 20, 21]  # Default peak engagement windows

    return hours


def load_vault_types(conn: sqlite3.Connection, creator_id: str) -> list[int]:
    """Load available content types from vault."""
    query = """
        SELECT content_type_id
        FROM vault_matrix
        WHERE creator_id = ? AND has_content = 1
    """
    cursor = conn.execute(query, (creator_id,))
    return [row["content_type_id"] for row in cursor.fetchall()]


# ============================================================================
# STEP 2: MATCH CONTENT - Filter by vault availability
# ============================================================================


def get_allowed_content_types(conn: sqlite3.Connection, creator_id: str) -> list[int]:
    """
    Get content types from vault_matrix where has_content=1.

    Step 2 content gate: Only content types with available content
    in the creator's vault are eligible for schedule slots.

    Args:
        conn: Database connection
        creator_id: Creator UUID

    Returns:
        List of content_type_id integers that have content available
    """
    strategy = ContentTypeStrategy(conn, creator_id)
    pools = strategy.get_allowed_content_types()
    return [p.content_type_id for p in pools]


def calculate_content_type_slot_allocation(
    conn: sqlite3.Connection,
    creator_id: str,
    total_ppv_slots: int,
) -> dict[str, int]:
    """
    Calculate how many slots each content type should get.

    Uses ContentTypeStrategy.allocate_slots_by_content_type() to distribute
    slots proportionally to expected earnings, with:
    - Minimum 1 slot per content type (variety floor)
    - Maximum 40% of slots for any single type (variety ceiling)

    Args:
        conn: Database connection
        creator_id: Creator UUID
        total_ppv_slots: Total number of PPV slots to allocate

    Returns:
        Dict mapping content type name to slot count
        Example: {'solo': 8, 'bg': 11, 'anal': 6, 'custom': 3}
    """
    strategy = ContentTypeStrategy(conn, creator_id)
    return strategy.allocate_slots_by_content_type(total_ppv_slots)


def load_stratified_pools(
    conn: sqlite3.Connection,
    creator_id: str,
    allowed_content_types: list[int],
    min_freshness: float = 30.0,
    filter_keywords: set[str] | None = None,
    min_uses_for_tested: int = 3,
) -> dict[int, StratifiedPools]:
    """
    Load captions stratified into PROVEN/GLOBAL_EARNER/DISCOVERY pools per content type.

    This function loads all eligible captions and partitions them into three tiers
    based on earnings data availability:
        - PROVEN: Has creator_avg_earnings > 0
        - GLOBAL_EARNER: Has global_avg_earnings > 0 (but no creator earnings)
        - DISCOVERY: No earnings data (uses performance proxy)

    Args:
        conn: Database connection
        creator_id: Creator UUID
        allowed_content_types: List of content_type_id to include
        min_freshness: Minimum freshness score (default 30)
        filter_keywords: Optional keywords to exclude from captions
        min_uses_for_tested: Threshold for tested status

    Returns:
        Dict mapping content_type_id to StratifiedPools object
    """
    # Get content type earnings for discovery pool calculations
    content_type_earnings = get_content_type_earnings(conn, creator_id)

    # Load all captions (existing function)
    all_captions = load_available_captions(
        conn, creator_id, min_freshness,
        vault_types=allowed_content_types,
        filter_keywords=filter_keywords,
        min_uses_for_tested=min_uses_for_tested
    )

    # Get content type names mapping
    type_names: dict[int, str] = {}
    for cap in all_captions:
        if cap.content_type_id and cap.content_type_name:
            type_names[cap.content_type_id] = cap.content_type_name

    # Initialize pools per content type
    pools: dict[int, StratifiedPools] = {}
    for ct_id in allowed_content_types:
        ct_name = type_names.get(ct_id, f"type_{ct_id}")
        ct_avg = content_type_earnings.get(ct_name, 50.0)
        pools[ct_id] = StratifiedPools(
            content_type_id=ct_id,
            content_type_name=ct_name,
            proven=[],
            global_earner=[],
            discovery=[],
            content_type_avg_earnings=ct_avg,
        )

    # Partition captions into pools
    for caption in all_captions:
        ct_id = caption.content_type_id
        if ct_id is None or ct_id not in pools:
            continue

        pool_type = determine_pool_type(caption)
        if pool_type == POOL_PROVEN:
            pools[ct_id].proven.append(caption)
        elif pool_type == POOL_GLOBAL_EARNER:
            pools[ct_id].global_earner.append(caption)
        else:
            pools[ct_id].discovery.append(caption)

    return pools


def identify_premium_slots(slots: list[dict]) -> list[dict]:
    """
    Return slots at peak hours (18:00, 21:00 - 6pm and 9pm).

    Premium slots receive only PROVEN pool captions for maximum
    revenue impact during peak engagement times.

    Args:
        slots: List of slot dicts with 'hour' key

    Returns:
        Filtered list of slots at premium hours
    """
    return [s for s in slots if s.get("hour") in PREMIUM_HOURS and s.get("type") == "ppv"]


def identify_discovery_slots(slots: list[dict], count: int) -> list[int]:
    """
    Distribute discovery slots evenly across the week.

    Discovery slots test new captions from the DISCOVERY pool to gather
    performance data. They are distributed evenly to avoid clustering.

    Args:
        slots: List of PPV slot dicts (already filtered to PPV type)
        count: Number of discovery slots to select

    Returns:
        List of slot indices (0-based) designated for discovery
    """
    ppv_slots = [s for s in slots if s.get("type") == "ppv"]
    if not ppv_slots or count <= 0:
        return []

    total = len(ppv_slots)
    if count >= total:
        return list(range(total))

    # Distribute evenly across the week
    indices = []
    step = total / count
    for i in range(count):
        idx = int(i * step + step / 2)
        idx = min(idx, total - 1)
        if idx not in indices:
            indices.append(idx)

    return indices


def load_available_captions(
    conn: sqlite3.Connection,
    creator_id: str,
    min_freshness: float = 30.0,
    vault_types: list[int] | None = None,
    filter_keywords: set[str] | None = None,
    min_uses_for_tested: int = 3
) -> list[Caption]:
    """
    Load available captions filtered by freshness and vault.

    Step 2 of pipeline: MATCH CONTENT

    Now includes earnings data from caption_creator_performance table
    for earnings-based caption selection (Phase 1-2 enhancement).
    """
    query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.caption_type,
            cb.content_type_id,
            ct.type_name AS content_type_name,
            cb.performance_score,
            cb.freshness_score,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.is_universal,
            -- Global earnings data
            cb.avg_earnings AS global_avg_earnings,
            cb.times_used AS global_times_used,
            -- Creator-specific earnings data (LEFT JOIN)
            ccp.avg_earnings AS creator_avg_earnings,
            ccp.times_used AS creator_times_used,
            -- Computed fields for sorting
            COALESCE(ccp.avg_earnings, cb.avg_earnings, 0) AS effective_earnings,
            CASE
                WHEN ccp.avg_earnings IS NOT NULL AND ccp.avg_earnings > 0 THEN 'creator'
                WHEN cb.avg_earnings IS NOT NULL AND cb.avg_earnings > 0 THEN 'global'
                ELSE 'none'
            END AS earnings_source,
            CASE
                WHEN ccp.times_used IS NULL OR ccp.times_used < ? THEN 1
                ELSE 0
            END AS is_untested
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        LEFT JOIN vault_matrix vm ON cb.creator_id = vm.creator_id
            AND cb.content_type_id = vm.content_type_id
        LEFT JOIN caption_creator_performance ccp
            ON cb.caption_id = ccp.caption_id AND ccp.creator_id = ?
        WHERE cb.is_active = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
          AND (vm.has_content = 1 OR vm.vault_id IS NULL OR cb.content_type_id IS NULL)
        ORDER BY effective_earnings DESC, cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 500
    """

    # Note: creator_id appears twice - once for JOIN, once for WHERE clause
    # Parameter order: min_uses_for_tested (CASE), creator_id (JOIN), creator_id (WHERE), min_freshness
    cursor = conn.execute(query, (min_uses_for_tested, creator_id, creator_id, min_freshness))

    captions = []
    for row in cursor.fetchall():
        # Skip if content type not in vault (when vault_types provided)
        if vault_types and row["content_type_id"]:
            if row["content_type_id"] not in vault_types:
                continue

        captions.append(Caption(
            caption_id=row["caption_id"],
            caption_text=row["caption_text"],
            caption_type=row["caption_type"],
            content_type_id=row["content_type_id"],
            content_type_name=row["content_type_name"],
            performance_score=row["performance_score"] or 50.0,
            freshness_score=row["freshness_score"] or 100.0,
            tone=row["tone"],
            emoji_style=row["emoji_style"],
            slang_level=row["slang_level"],
            is_universal=bool(row["is_universal"]),
            # NEW: Earnings fields
            creator_avg_earnings=row["creator_avg_earnings"],
            global_avg_earnings=row["global_avg_earnings"],
            creator_times_used=row["creator_times_used"] or 0,
            global_times_used=row["global_times_used"] or 0,
            earnings_source=row["earnings_source"],
            is_untested=bool(row["is_untested"])
        ))

    # Filter out captions containing restricted keywords
    if filter_keywords:
        original_count = len(captions)
        captions = [
            c for c in captions
            if not any(kw.lower() in c.caption_text.lower() for kw in filter_keywords)
        ]
        filtered_count = original_count - len(captions)
        if filtered_count > 0:
            print(f"[INFO] Filtered {filtered_count} captions by content restriction keywords")

    return captions


# ============================================================================
# STEP 3: MATCH PERSONA - Score by voice profile
# ============================================================================

# Import sophisticated persona matching from match_persona.py
# This enables text-based detection when database fields are NULL
from match_persona import (
    PersonaProfile as MatchPersonaProfile,
    calculate_persona_boost as full_persona_boost,
    detect_tone_from_text,
    detect_slang_level_from_text,
    get_emoji_frequency_category,
)


def apply_persona_scores(
    captions: list[Caption],
    profile: CreatorProfile,
    config: ScheduleConfig,
    use_text_detection: bool = True
) -> list[Caption]:
    """
    Apply persona boost scores to all captions using full match_persona logic.

    Step 3 of pipeline: MATCH PERSONA

    Now uses text-based detection when database fields are missing,
    dramatically improving persona matching coverage from ~30% to ~95%.

    Boost factors (cumulative, capped at 1.40x):
        - Primary tone match: 1.20x
        - Secondary tone match: 1.10x
        - Emoji frequency match: 1.05x
        - Slang level match: 1.05x
        - Sentiment alignment: 1.05x

    Args:
        captions: List of Caption objects to score
        profile: CreatorProfile with persona attributes
        config: ScheduleConfig with earnings weight settings
        use_text_detection: Enable text-based detection fallback (default: True)

    Returns:
        List of captions with persona_boost and combined_score set.
        (final_weight is calculated later in pool-based selection)
    """
    # Convert CreatorProfile to match_persona's PersonaProfile format
    persona = MatchPersonaProfile(
        creator_id=profile.creator_id,
        page_name=profile.page_name,
        primary_tone=profile.primary_tone,
        secondary_tone=getattr(profile, 'secondary_tone', None),
        emoji_frequency=profile.emoji_frequency,
        slang_level=profile.slang_level,
        avg_sentiment=profile.avg_sentiment,
    )

    for caption in captions:
        # Use FULL persona matching with text detection fallback
        # This is the KEY FIX: when caption.tone/slang_level/emoji_style are NULL,
        # the full_persona_boost function will analyze caption_text to detect them
        match_result = full_persona_boost(
            caption_tone=caption.tone,
            caption_emoji_style=caption.emoji_style,
            caption_slang_level=caption.slang_level,
            persona=persona,
            caption_text=caption.caption_text,
            use_text_detection=use_text_detection
        )

        caption.persona_boost = match_result.total_boost

        # Note: final_weight is calculated later in pool-based selection
        # using the new calculate_weight signature with pool_type and
        # content_type_avg_earnings. See lines ~1657 in pool-based selection.

        # Keep combined_score for backward compatibility (reporting/sorting)
        caption.combined_score = (
            caption.performance_score * 0.6 + caption.freshness_score * 0.4
        )

    return captions


# ============================================================================
# STEP 3B: EARNINGS-BASED WEIGHT CALCULATION
# ============================================================================

def get_earnings_stats(captions: list[Caption]) -> dict[str, float]:
    """
    Calculate earnings statistics for normalization.

    Returns dict with:
        - max_earnings: Maximum earnings across all captions
        - avg_earnings: Average earnings across captions with data
        - median_earnings: Median earnings
    """
    import statistics

    all_earnings = []
    for c in captions:
        earnings = c.creator_avg_earnings or c.global_avg_earnings
        if earnings and earnings > 0:
            all_earnings.append(earnings)

    if not all_earnings:
        return {'max_earnings': 100.0, 'avg_earnings': 50.0, 'median_earnings': 38.0}

    return {
        'max_earnings': max(all_earnings),
        'avg_earnings': statistics.mean(all_earnings),
        'median_earnings': statistics.median(all_earnings)
    }


# NOTE: calculate_earnings_based_weight has been refactored to weights.py
# Now using: from weights import calculate_weight


# ============================================================================
# STEP 4: BUILD STRUCTURE - Create weekly time slots
# ============================================================================

# Optimal days for paid page PPV distribution (campaign-style)
PAID_PAGE_OPTIMAL_DAYS = ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Peak hours for different contexts
PEAK_HOURS_MORNING = [10, 11]
PEAK_HOURS_AFTERNOON = [14, 15]
PEAK_HOURS_EVENING = [18, 19, 20, 21]


def _get_optimal_time_for_day(day: str, best_hours: list[int] | None = None) -> time:
    """
    Get the optimal posting time for a specific day.

    Args:
        day: Day name (e.g., "Tuesday")
        best_hours: Creator's best performing hours

    Returns:
        time object for optimal posting
    """
    # Use creator's best hour if available
    if best_hours and len(best_hours) > 0:
        hour = best_hours[0]
    else:
        # Default to evening peak (highest engagement)
        hour = 20

    # Add some variation based on day
    day_offsets = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": -1,
        "Thursday": 0,
        "Friday": 1,
        "Saturday": 2,
        "Sunday": 0,
    }
    hour += day_offsets.get(day, 0)
    hour = max(10, min(21, hour))  # Clamp to reasonable hours

    minute = random.choice([0, 15, 30, 45])
    return time(hour=hour, minute=minute)


def _get_staggered_time(ppv_index: int, total_ppv: int, best_hours: list[int] | None = None) -> time:
    """
    Get staggered posting time for multiple PPV in a day.

    Args:
        ppv_index: 0-based index of this PPV in the day
        total_ppv: Total number of PPV for this day
        best_hours: Creator's best performing hours

    Returns:
        time object with appropriate spacing
    """
    if best_hours and len(best_hours) >= total_ppv:
        # Use creator's best hours directly
        hour = best_hours[ppv_index % len(best_hours)]
    else:
        # Default time slots with 4-hour spacing
        default_slots = [10, 14, 18, 21]
        hour = default_slots[ppv_index % len(default_slots)]

    minute = random.choice([0, 15, 30, 45])
    return time(hour=hour, minute=minute)


def build_weekly_slots(
    config: ScheduleConfig,
    best_hours: list[int] | None = None
) -> list[dict[str, Any]]:
    """
    Build weekly time slots based on volume level with proper spacing.

    Step 4 of pipeline: BUILD STRUCTURE

    Handles paid vs free pages differently:
    - Paid pages: Distribute PPV across optimal days (weekly, campaign-style)
    - Free pages: Daily distribution with consistent volume

    Ensures minimum 3-hour spacing between PPV slots by selecting hours
    that are at least 4 hours apart (to allow for minute variation).
    """
    if best_hours is None or not best_hours:
        best_hours = [8, 12, 16, 20]  # Default hours with 4-hour gaps

    slots = []
    slot_id = 0

    # Check if this is a paid page with weekly volume
    is_paid_page = config.is_paid_page or config.page_type == "paid"
    has_weekly_strategy = (
        config.volume_strategy is not None
        and config.volume_period == "week"
    )

    if is_paid_page and has_weekly_strategy:
        # PAID PAGE: Campaign-style weekly distribution
        # Distribute PPV across optimal days of the week
        weekly_ppv = config.ppv_per_week or (config.ppv_per_day * 7)

        # Get optimal days for this creator
        optimal_days = PAID_PAGE_OPTIMAL_DAYS.copy()
        if config.volume_strategy and config.volume_strategy.optimal_days:
            optimal_days = config.volume_strategy.optimal_days

        # Calculate how many PPV per optimal day
        ppv_per_optimal_day = max(1, weekly_ppv // len(optimal_days))
        remaining_ppv = weekly_ppv

        current_date = config.week_start
        while current_date <= config.week_end and remaining_ppv > 0:
            day_name = current_date.strftime("%A")

            if day_name in optimal_days:
                # Schedule PPV for this optimal day
                day_ppv_count = min(ppv_per_optimal_day, remaining_ppv)

                if day_ppv_count == 1:
                    # Single PPV: use optimal time
                    optimal_time = _get_optimal_time_for_day(day_name, best_hours)
                    slot_id += 1
                    slots.append({
                        "slot_id": slot_id,
                        "date": current_date.isoformat(),
                        "day_name": day_name,
                        "time": optimal_time.strftime("%H:%M"),
                        "hour": optimal_time.hour,
                        "type": "ppv",
                        "priority": 3
                    })
                    remaining_ppv -= 1
                else:
                    # Multiple PPV: use spaced hours
                    ppv_hours = select_spaced_hours_strict(best_hours, day_ppv_count)
                    for i, hour in enumerate(ppv_hours):
                        if remaining_ppv <= 0:
                            break
                        slot_id += 1
                        minute = random.choice([0, 15, 30, 45])
                        slots.append({
                            "slot_id": slot_id,
                            "date": current_date.isoformat(),
                            "day_name": day_name,
                            "time": f"{hour:02d}:{minute:02d}",
                            "hour": hour,
                            "type": "ppv",
                            "priority": 3 if i == 0 else 5
                        })
                        remaining_ppv -= 1

            current_date += timedelta(days=1)

    else:
        # FREE PAGE: Daily distribution (original behavior)
        # Generate available hours with proper spacing
        available_hours = generate_spaced_hours(best_hours, config.ppv_per_day)

        current_date = config.week_start
        while current_date <= config.week_end:
            day_name = current_date.strftime("%A")

            # Generate PPV slots for this day with proper spacing
            # Use 4-hour minimum to account for minute variation
            ppv_hours = select_spaced_hours_strict(available_hours, config.ppv_per_day)

            for hour in ppv_hours:
                slot_id += 1
                # Add some minute variation (0, 15, 30, 45)
                minute = random.choice([0, 15, 30, 45])
                slots.append({
                    "slot_id": slot_id,
                    "date": current_date.isoformat(),
                    "day_name": day_name,
                    "time": f"{hour:02d}:{minute:02d}",
                    "hour": hour,
                    "type": "ppv",
                    "priority": 3 if hour in best_hours[:3] else 5
                })

            current_date += timedelta(days=1)

    # NEW: Wall post slots (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and getattr(config, 'enable_wall_posts', False):
        wall_slots = generate_wall_post_slots(
            config,
            config.week_start.isoformat(),
            config.week_end.isoformat(),
            start_slot_id=slot_id
        )
        slots.extend(wall_slots)
        slot_id += len(wall_slots)

    # NEW: Poll slots (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and getattr(config, 'enable_polls', False):
        poll_slots = generate_poll_slots(
            config,
            config.week_start.isoformat(),
            start_slot_id=slot_id
        )
        slots.extend(poll_slots)
        slot_id += len(poll_slots)

    # Sort by datetime
    slots.sort(key=lambda s: (s["date"], s["time"]))

    return slots


def generate_spaced_hours(best_hours: list[int], min_count: int) -> list[int]:
    """Generate a list of hours with at least 3-hour spacing."""
    # Start with best performing hours
    available = list(best_hours)

    # Add more hours if needed, ensuring 3-hour gaps
    all_hours = list(range(8, 23))  # 8 AM to 10 PM
    for hour in all_hours:
        if hour not in available:
            # Check if this hour has enough spacing from existing hours
            has_space = all(abs(hour - h) >= 3 for h in available)
            if has_space:
                available.append(hour)

    available.sort()
    return available


def select_spaced_hours(available_hours: list[int], count: int) -> list[int]:
    """
    Select hours ensuring minimum 3-hour spacing between them.

    Uses a greedy algorithm that prioritizes best hours while maintaining spacing.
    Will NOT relax spacing constraint - returns fewer hours if needed.
    """
    if count <= 0:
        return []

    # Sort available hours (prefer distributing across the day)
    sorted_hours = sorted(available_hours)

    # Try to select hours with 3+ hour spacing
    selected = []

    # Start with early morning, then fill in with spacing
    for hour in sorted_hours:
        if len(selected) >= count:
            break

        # Check spacing with all already selected hours
        has_space = all(abs(hour - h) >= MIN_PPV_SPACING_HOURS for h in selected)
        if has_space:
            selected.append(hour)

    # If we still need more, try again with remaining hours
    if len(selected) < count:
        remaining = [h for h in sorted_hours if h not in selected]
        for hour in remaining:
            if len(selected) >= count:
                break
            has_space = all(abs(hour - h) >= MIN_PPV_SPACING_HOURS for h in selected)
            if has_space:
                selected.append(hour)

    selected.sort()
    return selected


def select_spaced_hours_strict(available_hours: list[int], count: int) -> list[int]:
    """
    Select hours ensuring minimum 4-hour spacing between them.

    This stricter spacing (4 hours vs 3) ensures that even with +/- 45 minute
    variation on each slot, the final times will always be 3+ hours apart.

    Example: Hour 8 (+45min) = 8:45, Hour 12 (+0min) = 12:00 -> 3.25h apart
    """
    if count <= 0:
        return []

    # Use 4-hour minimum spacing to account for minute variation
    MIN_STRICT_SPACING = 4

    # Fixed ideal schedule with guaranteed 4-hour spacing
    # ALL slots must be 4+ hours apart to ensure 3+ hour gap after minute variation
    # With +45min worst case: 4h - 0.75h - 0.75h = 2.5h (still need 4h base)
    ideal_schedules = {
        2: [10, 18],  # 8-hour gap
        3: [8, 14, 20],  # 6-hour gaps
        4: [8, 12, 16, 20],  # 4-hour gaps (max 4 PPV with 4h spacing in 14h day)
        5: [6, 10, 14, 18, 22],  # 4-hour gaps (extended 16h day for 5 PPV)
    }

    # Use the fixed schedule for the requested count
    if count in ideal_schedules:
        selected = list(ideal_schedules[count])
    else:
        # For 1 or more than 5, use a simple approach
        selected = []
        for hour in [10, 14, 18, 22, 8]:
            if len(selected) >= count:
                break
            has_space = all(abs(hour - h) >= MIN_STRICT_SPACING for h in selected)
            if has_space:
                selected.append(hour)

    # Try to substitute with best performing hours where possible
    # Only if they maintain the spacing requirement
    sorted_best = sorted(available_hours)
    for best_hour in sorted_best:
        # Try to replace a similar ideal hour with this best hour
        for i, ideal_hour in enumerate(selected):
            # If best hour is close to ideal hour and maintains spacing
            if abs(best_hour - ideal_hour) <= 2:  # Within 2 hours of ideal slot
                # Check if substitution maintains spacing
                other_hours = [h for j, h in enumerate(selected) if j != i]
                has_space = all(abs(best_hour - h) >= MIN_STRICT_SPACING for h in other_hours)
                if has_space and best_hour not in selected:
                    selected[i] = best_hour
                    break

    selected.sort()
    return selected[:count]


# ============================================================================
# STEP 5: ASSIGN CAPTIONS - Weighted selection (Vose Alias)
# ============================================================================

def get_next_content_type(previous_type: str | None, available_types: set[str]) -> str | None:
    """
    Get next content type following rotation pattern.

    NEVER returns same type as previous (content rotation rule).
    """
    if not available_types:
        return None

    # Filter out previous type
    candidates = [t for t in available_types if t != previous_type]
    if not candidates:
        # If only one type available, use it (shouldn't happen normally)
        return list(available_types)[0] if available_types else None

    # Prefer types in rotation order
    for rotation_type in ROTATION_ORDER:
        if rotation_type in candidates:
            return rotation_type

    # Fall back to random from remaining
    return random.choice(candidates)


def partition_captions_by_testing_status(
    captions: list[Caption],
    min_uses: int = 3
) -> tuple[list[Caption], list[Caption]]:
    """
    Partition captions into tested and untested groups.

    Args:
        captions: All available captions
        min_uses: Minimum uses to be considered "tested"

    Returns:
        Tuple of (tested_captions, untested_captions)
    """
    tested = []
    untested = []

    for caption in captions:
        if caption.is_untested or (caption.creator_times_used or 0) < min_uses:
            untested.append(caption)
        else:
            tested.append(caption)

    return tested, untested


def calculate_reserved_slots(
    total_slots: int,
    reserved_ratio: float,
    untested_count: int
) -> int:
    """
    Calculate number of slots to reserve for untested captions.

    Args:
        total_slots: Total PPV slots in the schedule
        reserved_ratio: Target ratio for untested (e.g., 0.15 for 15%)
        untested_count: Number of untested captions available

    Returns:
        Number of slots to reserve (capped by available untested captions)
    """
    target_reserved = int(total_slots * reserved_ratio)
    # Cap at available untested captions
    return min(target_reserved, untested_count)


def _select_from_pool(
    pool: list[Caption],
    selector: VoseAliasSelector | None,
    used_ids: set[int],
    target_type: str | None,
    previous_type: str | None,
    max_attempts: int = 50
) -> Caption | None:
    """Helper to select from a caption pool with constraints."""
    # First try: match target content type
    if target_type:
        type_candidates = [
            c for c in pool
            if c.content_type_name == target_type and c.caption_id not in used_ids
        ]
        if type_candidates:
            weights = [c.final_weight for c in type_candidates]
            total = sum(weights)
            if total > 0:
                probs = [w / total for w in weights]
                return random.choices(type_candidates, weights=probs, k=1)[0]

    # Second try: any caption avoiding same type consecutively
    if selector:
        for _ in range(max_attempts):
            candidate = selector.select()
            if candidate.caption_id not in used_ids:
                if candidate.content_type_name != previous_type or previous_type is None:
                    return candidate
                elif len(used_ids) > len(pool) - 5:
                    # Near exhaustion, relax rotation constraint
                    return candidate

    # Fallback: first unused caption from pool
    for c in pool:
        if c.caption_id not in used_ids:
            return c

    return None


def _select_from_stratified_pool(
    pools: dict[int, StratifiedPools],
    target_content_type: str | None,
    slot_tier: str,  # "premium", "standard", or "discovery"
    used_ids: set[int],
    previous_type: str | None,
    persona: dict[str, str],
    config: ScheduleConfig,
    max_attempts: int = 50
) -> tuple[Caption | None, str]:
    """
    Select a caption from stratified pools based on slot tier.

    Args:
        pools: Dict mapping content_type_id to StratifiedPools
        target_content_type: Preferred content type name (may be None)
        slot_tier: "premium" (PROVEN only), "standard" (PROVEN+GLOBAL), "discovery" (DISCOVERY)
        used_ids: Set of already-used caption IDs
        previous_type: Previous content type (for rotation)
        persona: Creator persona dict for boost calculation
        config: Schedule configuration
        max_attempts: Maximum selection attempts

    Returns:
        Tuple of (selected Caption or None, pool_type string)
    """
    # Determine which pool tiers to search based on slot_tier
    if slot_tier == "premium":
        pool_priority = [POOL_PROVEN]
    elif slot_tier == "discovery":
        pool_priority = [POOL_DISCOVERY, POOL_GLOBAL_EARNER]
    else:  # standard
        pool_priority = [POOL_PROVEN, POOL_GLOBAL_EARNER]

    # Find matching content type pools
    target_pools: list[StratifiedPools] = []
    if target_content_type:
        for ct_id, pool in pools.items():
            if pool.content_type_name == target_content_type:
                target_pools.append(pool)
                break

    # If no target match, try any content type except previous
    if not target_pools:
        for ct_id, pool in pools.items():
            if pool.content_type_name != previous_type:
                target_pools.append(pool)

    # Try each pool tier in priority order
    for pool_type in pool_priority:
        for sp in target_pools:
            if pool_type == POOL_PROVEN:
                candidates = sp.proven
            elif pool_type == POOL_GLOBAL_EARNER:
                candidates = sp.global_earner
            else:
                candidates = sp.discovery

            # Filter to unused captions
            available = [c for c in candidates if c.caption_id not in used_ids]
            if not available:
                continue

            # Calculate max_earnings for this pool
            max_earnings = get_max_earnings(available, pool_type)

            # Calculate weights for all available captions
            for caption in available:
                caption.final_weight = calculate_weight(
                    caption,
                    pool_type=pool_type,
                    content_type_avg_earnings=sp.content_type_avg_earnings,
                    max_earnings=max_earnings,
                    persona_boost=caption.persona_boost,
                )

            # Select using weighted random
            weights = [c.final_weight for c in available]
            total_weight = sum(weights)
            if total_weight > 0:
                selected = random.choices(available, weights=weights, k=1)[0]
                return selected, pool_type

            # Fallback to first available
            if available:
                return available[0], pool_type

    return None, "none"


def assign_captions_to_slots_pooled(
    slots: list[dict[str, Any]],
    pools: dict[int, StratifiedPools],
    persona: dict[str, str],
    content_type_allocation: dict[str, int],
    config: ScheduleConfig,
    discovery_ratio: float = 0.15,
    premium_ratio: float = 0.25,
) -> list[ScheduleItem]:
    """
    Assign captions to time slots using pool-based selection.

    Step 5 of pipeline: ASSIGN CAPTIONS (Pool-Based Version)

    Slot allocation:
    - Premium (25%): Peak hours (18:00, 21:00), PROVEN pool only
    - Standard (60%): All other hours, PROVEN + GLOBAL_EARNER
    - Discovery (15%): Distributed evenly, DISCOVERY pool

    Content type distribution follows content_type_allocation weights.

    Args:
        slots: List of slot dicts with date, time, hour, type keys
        pools: Dict mapping content_type_id to StratifiedPools
        persona: Creator persona dict for boost calculation
        content_type_allocation: Dict mapping content type name to slot count
        config: Schedule configuration
        discovery_ratio: Fraction of slots for discovery (default 0.15)
        premium_ratio: Fraction of slots for premium (default 0.25)

    Returns:
        List of ScheduleItem objects
    """
    if not pools:
        return []

    # Get PPV slots only
    ppv_slots = [s for s in slots if s.get("type") == "ppv"]
    total_ppv_slots = len(ppv_slots)

    if total_ppv_slots == 0:
        return []

    # Calculate slot counts for each tier
    discovery_count = int(total_ppv_slots * discovery_ratio)
    premium_count = int(total_ppv_slots * premium_ratio)
    standard_count = total_ppv_slots - discovery_count - premium_count

    # Identify slot tiers
    premium_slot_indices: set[int] = set()
    discovery_slot_indices: set[int] = set()

    # Premium slots: at peak hours (18:00, 21:00)
    for i, slot in enumerate(ppv_slots):
        if slot.get("hour") in PREMIUM_HOURS:
            if len(premium_slot_indices) < premium_count:
                premium_slot_indices.add(i)

    # Discovery slots: evenly distributed (excluding premium)
    discovery_candidates = [i for i in range(total_ppv_slots) if i not in premium_slot_indices]
    discovery_slot_indices = set(identify_discovery_slots(
        [ppv_slots[i] for i in discovery_candidates],
        discovery_count
    ))
    # Map back to original indices
    mapped_discovery = set()
    for idx, orig_idx in enumerate(discovery_candidates):
        if idx in discovery_slot_indices:
            mapped_discovery.add(orig_idx)
    discovery_slot_indices = mapped_discovery

    # Track content type usage vs allocation
    content_type_used: dict[str, int] = {ct: 0 for ct in content_type_allocation.keys()}
    available_types = set(content_type_allocation.keys())

    # Build items
    items: list[ScheduleItem] = []
    used_caption_ids: set[int] = set()
    previous_content_type: str | None = None

    # Log slot tier distribution
    logger.info(
        f"Pool-based selection: {premium_count} premium, {standard_count} standard, "
        f"{discovery_count} discovery slots"
    )

    for slot_index, slot in enumerate(ppv_slots):
        # Determine slot tier
        if slot_index in premium_slot_indices:
            slot_tier = "premium"
        elif slot_index in discovery_slot_indices:
            slot_tier = "discovery"
        else:
            slot_tier = "standard"

        # Determine target content type based on allocation and rotation
        target_type = None
        for ct_name in available_types:
            if ct_name == previous_content_type:
                continue
            allocated = content_type_allocation.get(ct_name, 0)
            used = content_type_used.get(ct_name, 0)
            if used < allocated:
                target_type = ct_name
                break

        # If all at allocation, pick any except previous
        if not target_type:
            target_type = get_next_content_type(previous_content_type, available_types)

        # Select caption from appropriate pool
        selected_caption, pool_type = _select_from_stratified_pool(
            pools=pools,
            target_content_type=target_type,
            slot_tier=slot_tier,
            used_ids=used_caption_ids,
            previous_type=previous_content_type,
            persona=persona,
            config=config,
        )

        if selected_caption:
            used_caption_ids.add(selected_caption.caption_id)
            previous_content_type = selected_caption.content_type_name

            # Update content type usage
            ct_name = selected_caption.content_type_name or "unknown"
            content_type_used[ct_name] = content_type_used.get(ct_name, 0) + 1

            # Calculate suggested price
            base_price = 14.99 if config.page_type == "paid" else 9.99
            if selected_caption.performance_score >= 80:
                base_price *= 1.2
            elif selected_caption.performance_score < 50:
                base_price *= 0.9

            # Build selection notes
            selection_note = (
                f"Pool: {pool_type} | Tier: {slot_tier} | "
                f"Boost: {selected_caption.persona_boost:.2f}x"
            )

            items.append(ScheduleItem(
                item_id=slot["slot_id"],
                creator_id=config.creator_id,
                scheduled_date=slot["date"],
                scheduled_time=slot["time"],
                item_type="ppv",
                caption_id=selected_caption.caption_id,
                caption_text=selected_caption.caption_text,
                content_type_id=selected_caption.content_type_id,
                content_type_name=selected_caption.content_type_name,
                suggested_price=round(base_price, 2),
                freshness_score=selected_caption.freshness_score,
                performance_score=selected_caption.performance_score,
                priority=slot["priority"],
                notes=selection_note
            ))

    # Log content type distribution
    logger.info(f"Content type distribution: {content_type_used}")

    return items


def assign_captions_to_slots(
    slots: list[dict[str, Any]],
    captions: list[Caption],
    config: ScheduleConfig,
    pools: dict[int, StratifiedPools] | None = None,
    persona: dict[str, str] | None = None,
    content_type_allocation: dict[str, int] | None = None,
) -> list[ScheduleItem]:
    """
    Assign captions to slots using pool-based or legacy selection.

    Step 5 of pipeline: ASSIGN CAPTIONS

    If pools, persona, and content_type_allocation are provided, uses the new
    pool-based selection. Otherwise falls back to legacy hybrid selection.

    Args:
        slots: List of slot dicts
        captions: List of Caption objects (legacy mode)
        config: Schedule configuration
        pools: Optional stratified pools for pool-based selection
        persona: Optional creator persona dict
        content_type_allocation: Optional content type slot allocation

    Returns:
        List of ScheduleItem objects
    """
    # Use pool-based selection if pools are provided
    if pools is not None and persona is not None and content_type_allocation is not None:
        return assign_captions_to_slots_pooled(
            slots=slots,
            pools=pools,
            persona=persona,
            content_type_allocation=content_type_allocation,
            config=config,
            discovery_ratio=config.reserved_slot_ratio,
            premium_ratio=0.25,
        )

    # Legacy fallback: hybrid earnings-based selection
    if not captions:
        return []

    # Partition captions by testing status
    tested, untested = partition_captions_by_testing_status(
        captions, config.min_uses_for_tested
    )

    # Count PPV slots
    ppv_slots = [s for s in slots if s["type"] == "ppv"]
    total_ppv_slots = len(ppv_slots)

    # Calculate reserved slots for discovery
    reserved_count = calculate_reserved_slots(
        total_ppv_slots,
        config.reserved_slot_ratio,
        len(untested)
    )

    # Distribute reserved slots evenly across the week
    reserved_slot_indices = set()
    if reserved_count > 0 and total_ppv_slots > 0:
        reserved_count = min(reserved_count, total_ppv_slots)
        step = total_ppv_slots // reserved_count if reserved_count > 0 else total_ppv_slots
        for i in range(reserved_count):
            idx = min(i * step + step // 2, total_ppv_slots - 1)
            reserved_slot_indices.add(idx)

    # Build Vose Alias selectors for each pool
    tested_selector = None
    untested_selector = None

    if tested:
        try:
            tested_selector = VoseAliasSelector(tested, lambda c: c.final_weight)
        except ValueError as e:
            logger.warning(f"Failed to construct tested_selector: {e}, falling back to max-weight")

    if untested:
        try:
            untested_selector = VoseAliasSelector(
                untested,
                lambda c: c.freshness_score * c.persona_boost
            )
        except ValueError as e:
            logger.warning(f"Failed to construct untested_selector: {e}, falling back to max-weight")

    items = []
    used_caption_ids: set[int] = set()
    previous_content_type: str | None = None
    ppv_slot_index = 0

    # Group captions by content type for rotation
    captions_by_type: dict[str, list[Caption]] = {}
    for cap in captions:
        ctype = cap.content_type_name or "unknown"
        if ctype not in captions_by_type:
            captions_by_type[ctype] = []
        captions_by_type[ctype].append(cap)

    available_types = set(captions_by_type.keys())

    for slot in slots:
        if slot["type"] != "ppv":
            continue

        is_reserved_slot = ppv_slot_index in reserved_slot_indices
        ppv_slot_index += 1

        target_type = get_next_content_type(previous_content_type, available_types)
        selected_caption: Caption | None = None

        if is_reserved_slot and untested:
            selected_caption = _select_from_pool(
                untested, untested_selector, used_caption_ids,
                target_type, previous_content_type
            )

        if not selected_caption and tested:
            selected_caption = _select_from_pool(
                tested, tested_selector, used_caption_ids,
                target_type, previous_content_type
            )

        if not selected_caption:
            unused = [c for c in captions if c.caption_id not in used_caption_ids]
            if unused:
                logger.debug("Using fallback max-weight selection for slot")
                selected_caption = max(unused, key=lambda c: c.final_weight)

        if selected_caption:
            used_caption_ids.add(selected_caption.caption_id)
            previous_content_type = selected_caption.content_type_name

            base_price = 14.99 if config.page_type == "paid" else 9.99
            if selected_caption.performance_score >= 80:
                base_price *= 1.2
            elif selected_caption.performance_score < 50:
                base_price *= 0.9

            selection_note = f"Boost: {selected_caption.persona_boost:.2f}x | "
            selection_note += f"Earnings: {selected_caption.earnings_source}"
            if is_reserved_slot:
                selection_note += " [DISCOVERY]"

            items.append(ScheduleItem(
                item_id=slot["slot_id"],
                creator_id=config.creator_id,
                scheduled_date=slot["date"],
                scheduled_time=slot["time"],
                item_type="ppv",
                caption_id=selected_caption.caption_id,
                caption_text=selected_caption.caption_text,
                content_type_id=selected_caption.content_type_id,
                content_type_name=selected_caption.content_type_name,
                suggested_price=round(base_price, 2),
                freshness_score=selected_caption.freshness_score,
                performance_score=selected_caption.performance_score,
                priority=slot["priority"],
                notes=selection_note
            ))

    return items


# ============================================================================
# STEP 6: GENERATE FOLLOW-UPS - Create follow-ups (if enabled)
# ============================================================================

def generate_follow_ups(
    items: list[ScheduleItem],
    config: ScheduleConfig
) -> list[ScheduleItem]:
    """
    Generate follow-up bump messages for each PPV.

    Step 6 of pipeline: GENERATE FOLLOW-UPS

    Timing: 15-45 minutes after each PPV (randomized)
    """
    if not config.enable_follow_ups:
        return items

    all_items = list(items)
    next_id = max((item.item_id for item in items), default=0) + 1

    for item in items:
        if item.item_type != "ppv":
            continue

        # Calculate follow-up time (15-45 minutes after PPV)
        ppv_time = datetime.strptime(
            f"{item.scheduled_date} {item.scheduled_time}",
            "%Y-%m-%d %H:%M"
        )
        follow_up_minutes = random.randint(FOLLOW_UP_MIN_MINUTES, FOLLOW_UP_MAX_MINUTES)
        follow_up_time = ppv_time + timedelta(minutes=follow_up_minutes)

        # Create follow-up item
        bump_message = random.choice(BUMP_MESSAGES)

        all_items.append(ScheduleItem(
            item_id=next_id,
            creator_id=config.creator_id,
            scheduled_date=follow_up_time.strftime("%Y-%m-%d"),
            scheduled_time=follow_up_time.strftime("%H:%M"),
            item_type="bump",
            caption_text=bump_message,
            is_follow_up=True,
            parent_item_id=item.item_id,
            priority=6,
            notes=f"Follow-up for PPV #{item.item_id}"
        ))

        next_id += 1

    # Sort by datetime
    all_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))

    return all_items


# ============================================================================
# STEP 6B: CONTEXTUAL FOLLOW-UPS - Context-aware bumps (full mode)
# ============================================================================

def generate_contextual_follow_ups(
    items: list[ScheduleItem],
    config: ScheduleConfig,
    profile: CreatorProfile
) -> list[ScheduleItem]:
    """
    Generate context-aware follow-up messages using FollowupGenerator.

    Step 6B of pipeline: CONTEXTUAL FOLLOW-UPS (full mode only)

    Unlike generic bumps, these follow-ups:
    - Reference the original PPV content naturally
    - Use strategies based on time of day and content type
    - Match the creator's tone and emoji style
    - Vary timing based on context (15-45 minutes)

    Args:
        items: List of scheduled items (PPVs)
        config: Schedule configuration
        profile: Creator profile for persona matching

    Returns:
        List of items with contextual follow-ups added
    """
    if not config.enable_follow_ups:
        return items

    if not FOLLOWUP_GENERATOR_AVAILABLE:
        print("Warning: FollowupGenerator not available, using generic bumps", file=sys.stderr)
        return generate_follow_ups(items, config)

    generator = FollowupGenerator({
        "creator_id": profile.creator_id,
        "page_name": profile.page_name,
        "primary_tone": profile.primary_tone,
        "emoji_frequency": profile.emoji_frequency,
        "slang_level": profile.slang_level,
    })

    all_items = list(items)
    next_id = max((item.item_id for item in items), default=0) + 1

    # Collect contexts for batch generation
    ppv_contexts: list[FollowUpContext] = []
    ppv_items: list[ScheduleItem] = []

    for item in items:
        if item.item_type != "ppv":
            continue

        ppv_dt = datetime.strptime(
            f"{item.scheduled_date} {item.scheduled_time}",
            "%Y-%m-%d %H:%M"
        )

        context = FollowUpContext(
            original_caption=item.caption_text or "",
            content_type=item.content_type_name or "default",
            creator_tone=profile.primary_tone,
            emoji_frequency=profile.emoji_frequency,
            price=item.suggested_price,
            day_of_week=ppv_dt.weekday(),
            hour=ppv_dt.hour
        )
        ppv_contexts.append(context)
        ppv_items.append(item)

    # Generate follow-ups in batch (avoids repetition)
    followups = generator.generate_batch(ppv_contexts, avoid_repetition=True)

    # Create follow-up schedule items
    for item, followup in zip(ppv_items, followups):
        ppv_dt = datetime.strptime(
            f"{item.scheduled_date} {item.scheduled_time}",
            "%Y-%m-%d %H:%M"
        )
        follow_up_time = ppv_dt + timedelta(minutes=followup.timing_minutes)

        all_items.append(ScheduleItem(
            item_id=next_id,
            creator_id=config.creator_id,
            scheduled_date=follow_up_time.strftime("%Y-%m-%d"),
            scheduled_time=follow_up_time.strftime("%H:%M"),
            item_type="bump",
            caption_text=followup.text,
            is_follow_up=True,
            parent_item_id=item.item_id,
            priority=6,
            notes=f"Context: {followup.context_type} | Timing: {followup.timing_minutes}min"
        ))
        next_id += 1

    # Sort by datetime
    all_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))

    return all_items


# ============================================================================
# STEP 7: APPLY DRIP WINDOWS - Enforce no-PPV zones (if enabled)
# ============================================================================

def apply_drip_windows(
    items: list[ScheduleItem],
    config: ScheduleConfig
) -> list[ScheduleItem]:
    """
    Apply drip windows - 4-8 hour periods with NO buying opportunities.

    Step 7 of pipeline: APPLY DRIP WINDOWS

    During drip windows (typically 2 PM - 10 PM):
    - NO PPV messages allowed
    - Replace with drip content markers or wall bumps
    """
    if not config.enable_drip_windows:
        return items

    modified_items = []

    for item in items:
        hour = int(item.scheduled_time.split(":")[0])

        # Check if item falls within drip window
        if DRIP_WINDOW_START_HOUR <= hour < DRIP_WINDOW_END_HOUR:
            if item.item_type == "ppv":
                # Convert PPV to drip marker during drip window
                modified_items.append(ScheduleItem(
                    item_id=item.item_id,
                    creator_id=item.creator_id,
                    scheduled_date=item.scheduled_date,
                    scheduled_time=item.scheduled_time,
                    item_type="drip",
                    caption_text="[DRIP WINDOW - No PPV]",
                    priority=7,
                    notes="Drip window active - original PPV moved"
                ))
            else:
                modified_items.append(item)
        else:
            modified_items.append(item)

    return modified_items


# ============================================================================
# STEP 8: APPLY PAGE TYPE RULES - Paid vs Free rules (if enabled)
# ============================================================================

def apply_page_type_rules(
    items: list[ScheduleItem],
    config: ScheduleConfig
) -> list[ScheduleItem]:
    """
    Apply page-type specific rules for pricing and content.

    Step 8 of pipeline: APPLY PAGE TYPE RULES

    Paid pages: Campaign-style, premium pricing
    Free pages: Direct unlocks, standard pricing
    """
    if not config.enable_page_type_rules:
        return items

    for item in items:
        if item.item_type != "ppv":
            continue

        if config.page_type == "paid":
            # Premium pricing for paid pages
            if item.suggested_price:
                item.suggested_price = round(item.suggested_price * 1.1, 2)
            item.channel = "campaign"
        else:
            # Standard pricing for free pages
            if item.suggested_price:
                item.suggested_price = round(item.suggested_price * 0.9, 2)
            item.channel = "direct_unlock"

    return items


# ============================================================================
# STEP 9: VALIDATE & RETURN - Check business rules
# ============================================================================

def validate_schedule(
    items: list[ScheduleItem],
    config: ScheduleConfig
) -> list[ValidationIssue]:
    """
    Validate schedule against all business rules.

    Step 9 of pipeline: VALIDATE & RETURN

    Rules checked:
    1. PPV Spacing >= 3 hours (ERROR if violated)
    2. No duplicate captions (ERROR if violated)
    3. All freshness >= 30 (ERROR if violated)
    4. Content rotation (WARNING if same type consecutively)
    5. Follow-up timing 15-45 min (WARNING if outside)
    """
    issues = []

    # Check PPV spacing
    ppv_items = [item for item in items if item.item_type == "ppv"]
    ppv_items.sort(key=lambda x: (x.scheduled_date, x.scheduled_time))

    for i in range(1, len(ppv_items)):
        prev = ppv_items[i - 1]
        curr = ppv_items[i]

        prev_dt = datetime.strptime(f"{prev.scheduled_date} {prev.scheduled_time}", "%Y-%m-%d %H:%M")
        curr_dt = datetime.strptime(f"{curr.scheduled_date} {curr.scheduled_time}", "%Y-%m-%d %H:%M")

        gap_hours = (curr_dt - prev_dt).total_seconds() / 3600

        if gap_hours < MIN_PPV_SPACING_HOURS:
            issues.append(ValidationIssue(
                rule_name="ppv_spacing",
                severity="error",
                message=f"PPV spacing too close: {gap_hours:.1f}h between #{prev.item_id} and #{curr.item_id} (min {MIN_PPV_SPACING_HOURS}h)",
                item_ids=(prev.item_id, curr.item_id)
            ))

    # Check duplicate captions
    caption_ids: dict[int, list[int]] = {}
    for item in items:
        if item.caption_id:
            if item.caption_id not in caption_ids:
                caption_ids[item.caption_id] = []
            caption_ids[item.caption_id].append(item.item_id)

    for caption_id, item_ids in caption_ids.items():
        if len(item_ids) > 1:
            issues.append(ValidationIssue(
                rule_name="duplicate_captions",
                severity="error",
                message=f"Caption {caption_id} used {len(item_ids)} times in items {item_ids}",
                item_ids=tuple(item_ids)
            ))

    # Check freshness scores
    for item in items:
        if item.freshness_score < MIN_FRESHNESS_SCORE and item.item_type == "ppv":
            issues.append(ValidationIssue(
                rule_name="freshness_threshold",
                severity="error",
                message=f"Item #{item.item_id} has low freshness: {item.freshness_score:.1f} (min {MIN_FRESHNESS_SCORE})",
                item_ids=(item.item_id,)
            ))

    # Check content rotation
    previous_type = None
    consecutive_count = 0
    for item in sorted(items, key=lambda x: (x.scheduled_date, x.scheduled_time)):
        if item.item_type != "ppv":
            continue

        if item.content_type_name == previous_type:
            consecutive_count += 1
            if consecutive_count >= 2:
                issues.append(ValidationIssue(
                    rule_name="content_rotation",
                    severity="warning",
                    message=f"Same content type '{item.content_type_name}' used {consecutive_count + 1}x consecutively at item #{item.item_id}",
                    item_ids=(item.item_id,)
                ))
        else:
            consecutive_count = 0
            previous_type = item.content_type_name

    # Check follow-up timing
    items_by_id = {item.item_id: item for item in items}
    for item in items:
        if item.is_follow_up and item.parent_item_id:
            parent = items_by_id.get(item.parent_item_id)
            if parent:
                parent_dt = datetime.strptime(f"{parent.scheduled_date} {parent.scheduled_time}", "%Y-%m-%d %H:%M")
                item_dt = datetime.strptime(f"{item.scheduled_date} {item.scheduled_time}", "%Y-%m-%d %H:%M")
                gap_minutes = (item_dt - parent_dt).total_seconds() / 60

                if gap_minutes < FOLLOW_UP_MIN_MINUTES or gap_minutes > FOLLOW_UP_MAX_MINUTES:
                    issues.append(ValidationIssue(
                        rule_name="followup_timing",
                        severity="warning",
                        message=f"Follow-up #{item.item_id} timing: {gap_minutes:.0f}min (should be {FOLLOW_UP_MIN_MINUTES}-{FOLLOW_UP_MAX_MINUTES}min)",
                        item_ids=(item.item_id,)
                    ))

    return issues


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def generate_schedule(
    config: ScheduleConfig,
    conn: sqlite3.Connection
) -> ScheduleResult:
    """
    Generate a weekly schedule using the enhanced 12-step pipeline.

    Quick Mode (default): Steps 1-3, 5-9, 11-12 (no LLM processing)
    Full Mode: All 12 steps with LLM quality scoring, caption enhancement,
               and context-aware follow-ups

    Pipeline Steps:
        1. ANALYZE - Load creator profile and analytics
        2. MATCH CONTENT - Filter by vault availability
        3. MATCH PERSONA - Score by voice profile
        4. QUALITY SCORING - LLM-based caption quality (full mode only)
        5. BUILD STRUCTURE - Create weekly time slots
        6. ASSIGN CAPTIONS - Weighted selection (Vose Alias)
        7. CAPTION ENHANCEMENT - Minor authenticity tweaks (full mode only)
        8. GENERATE FOLLOW-UPS - Create follow-ups (context-aware in full mode)
        9. APPLY DRIP WINDOWS - Enforce no-PPV zones (if enabled)
        10. APPLY PAGE TYPE RULES - Paid vs Free rules (if enabled)
        11. VALIDATE - Check business rules
        12. RETURN - Package results
    """
    schedule_id = str(uuid.uuid4())[:8]

    result = ScheduleResult(
        schedule_id=schedule_id,
        creator_id=config.creator_id,
        creator_name=config.creator_name,
        display_name=config.creator_name,
        page_type=config.page_type,
        week_start=config.week_start.isoformat(),
        week_end=config.week_end.isoformat(),
        volume_level=config.volume_level,
        generated_at=datetime.now().isoformat()
    )

    # =========================================================================
    # AGENT SYSTEM INITIALIZATION (Phase 3 Integration)
    # =========================================================================
    agent_context: ScheduleContext | None = None
    agent_invoker: AgentInvoker | None = None

    if config.use_agents and AGENT_INVOKER_AVAILABLE:
        print(f"  [AGENT MODE] Initializing agent system...", file=sys.stderr)
        try:
            agent_invoker = AgentInvoker(db_path=str(DB_PATH))

            # Create shared context for inter-agent communication
            agent_context = ScheduleContext(
                creator_id=config.creator_id,
                week_start=config.week_start,
                week_end=config.week_end,
                mode=config.mode,
            )

            # PHASE 5: Agent availability validation at startup
            available_agents = agent_invoker.get_available_agents()
            required_agents = [
                "timezone-optimizer",
                "volume-calibrator",
                "content-strategy-optimizer",
                "revenue-optimizer",
                "multi-touch-sequencer",
                "validation-guardian",
            ]
            missing_agents = set(required_agents) - set(available_agents)

            if missing_agents:
                print(f"  [AGENT MODE] WARNING: Missing agents: {missing_agents}", file=sys.stderr)
                print(f"  [AGENT MODE] Expected location: ~/.claude/agents/eros-scheduling/", file=sys.stderr)
                print(f"  [AGENT MODE] Continuing with fallback mode for missing agents", file=sys.stderr)

            print(f"  [AGENT MODE] Available agents: {len(available_agents)}/{len(required_agents)}", file=sys.stderr)
            for agent in available_agents:
                print(f"    - {agent}", file=sys.stderr)

            result.agent_mode = "enabled" if len(available_agents) == len(required_agents) else "partial"

        except Exception as e:
            print(f"  [AGENT MODE] Warning: Agent initialization failed: {e}", file=sys.stderr)
            print(f"  [AGENT MODE] Falling back to standard pipeline", file=sys.stderr)
            agent_invoker = None
            agent_context = None
            result.agent_mode = "disabled"
    elif config.use_agents and not AGENT_INVOKER_AVAILABLE:
        print(f"  [AGENT MODE] Warning: Agent invoker not available (import failed)", file=sys.stderr)
        result.agent_mode = "disabled"

    # Step 1: ANALYZE - Load creator profile
    profile = load_creator_profile(conn, creator_id=config.creator_id)
    if not profile:
        result.validation_issues.append(ValidationIssue(
            rule_name="creator_not_found",
            severity="error",
            message=f"Creator not found: {config.creator_id}"
        ))
        result.validation_passed = False
        return result

    result.display_name = profile.display_name
    result.best_hours = profile.best_hours

    # =========================================================================
    # AGENT STEP 1A: VOLUME CALIBRATION (Before Step 2)
    # Agent: volume-calibrator - Optimizes volume targets based on performance data
    # =========================================================================
    if agent_invoker and agent_context:
        try:
            print(f"  [AGENT MODE] Invoking volume-calibrator...", file=sys.stderr)

            # Populate agent context with creator profile
            agent_context.creator_profile = AgentCreatorProfile(
                creator_id=profile.creator_id,
                page_name=profile.page_name,
                display_name=profile.display_name,
                page_type=profile.page_type,
                subscription_price=0.0,  # Not loaded in basic profile
                current_active_fans=profile.active_fans,
                performance_tier=1,  # Default tier
                current_total_earnings=0.0,
                current_avg_spend_per_txn=0.0,
                current_avg_earnings_per_fan=0.0,
                volume_level=profile.volume_level,
                ppv_per_day=config.ppv_per_day,
                bump_per_day=config.bump_per_day,
            )

            # Invoke timezone optimizer for timing strategy
            timing_strategy, timing_fallback = agent_invoker.invoke_timezone_optimizer(agent_context)
            agent_context.timing = timing_strategy

            if timing_fallback:
                result.agents_fallback.append("timezone-optimizer")
                print(f"  [AGENT MODE] timezone-optimizer: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("timezone-optimizer")
                print(f"  [AGENT MODE] timezone-optimizer: invoked successfully", file=sys.stderr)

            # Invoke page type optimizer for page-specific rules
            page_rules, page_fallback = agent_invoker.invoke_page_type_optimizer(agent_context)
            agent_context.page_type_rules = page_rules

            if page_fallback:
                result.agents_fallback.append("page-type-optimizer")
                print(f"  [AGENT MODE] page-type-optimizer: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("page-type-optimizer")
                print(f"  [AGENT MODE] page-type-optimizer: invoked successfully", file=sys.stderr)

        except Exception as e:
            print(f"  [AGENT MODE] Warning: Volume calibration agents failed: {e}", file=sys.stderr)
            result.agents_fallback.extend(["timezone-optimizer", "page-type-optimizer"])

    # Step 2: MATCH CONTENT - Filter by vault availability with content type gate
    # NEW: Get allowed content types from vault_matrix
    allowed_content_types = get_allowed_content_types(conn, config.creator_id)
    if not allowed_content_types:
        result.validation_issues.append(ValidationIssue(
            rule_name="no_content_types",
            severity="error",
            message="No content types found in vault_matrix. Cannot generate schedule."
        ))
        result.validation_passed = False
        return result

    logger.info(f"[Step 2] Content type gate: {len(allowed_content_types)} allowed types")

    # Load available captions
    captions = load_available_captions(
        conn, config.creator_id, config.min_freshness, profile.vault_types,
        filter_keywords=profile.filter_keywords,
        min_uses_for_tested=config.min_uses_for_tested
    )
    if not captions:
        result.validation_issues.append(ValidationIssue(
            rule_name="no_captions",
            severity="error",
            message="No eligible captions found with freshness >= 30"
        ))
        result.validation_passed = False
        return result

    # Load vault type names for result
    vault_query = """
        SELECT ct.type_name
        FROM vault_matrix vm
        JOIN content_types ct ON vm.content_type_id = ct.content_type_id
        WHERE vm.creator_id = ? AND vm.has_content = 1
    """
    cursor = conn.execute(vault_query, (config.creator_id,))
    result.vault_types = [row["type_name"] for row in cursor.fetchall()]

    # Step 3: MATCH PERSONA - Score by voice profile
    captions = apply_persona_scores(captions, profile, config)

    # NEW: Build persona dict for pool-based selection
    persona_dict = {
        "primary_tone": profile.primary_tone,
        "emoji_frequency": profile.emoji_frequency,
        "slang_level": profile.slang_level,
    }

    # NEW: Load stratified pools per content type (for pool-based selection)
    stratified_pools = load_stratified_pools(
        conn,
        config.creator_id,
        allowed_content_types,
        min_freshness=config.min_freshness,
        filter_keywords=profile.filter_keywords,
        min_uses_for_tested=config.min_uses_for_tested,
    )

    # Log pool statistics
    total_proven = sum(len(p.proven) for p in stratified_pools.values())
    total_global = sum(len(p.global_earner) for p in stratified_pools.values())
    total_discovery = sum(len(p.discovery) for p in stratified_pools.values())
    logger.info(
        f"[Step 2] Stratified pools loaded: "
        f"{total_proven} proven, {total_global} global_earner, {total_discovery} discovery"
    )
    for ct_id, pool in stratified_pools.items():
        logger.debug(
            f"  {pool.content_type_name}: "
            f"proven={len(pool.proven)}, global={len(pool.global_earner)}, "
            f"discovery={len(pool.discovery)}, avg_earnings=${pool.content_type_avg_earnings:.2f}"
        )

    # =========================================================================
    # AGENT STEP 3A: CONTENT STRATEGY OPTIMIZATION (After Step 3)
    # Agent: content-strategy-optimizer - Plans content rotation strategy
    # =========================================================================
    if agent_invoker and agent_context:
        try:
            print(f"  [AGENT MODE] Invoking content-strategy-optimizer...", file=sys.stderr)

            # Populate persona profile for content matching
            agent_context.persona_profile = PersonaProfile(
                creator_id=profile.creator_id,
                primary_tone=profile.primary_tone,
                emoji_frequency=profile.emoji_frequency,
                favorite_emojis="",  # Not available in basic profile
                slang_level=profile.slang_level,
                avg_sentiment=profile.avg_sentiment,
                avg_caption_length=0,  # Not available in basic profile
            )

            # Invoke content rotation architect for content strategy
            rotation_strategy, rotation_fallback = agent_invoker.invoke_content_rotation_architect(agent_context)
            agent_context.rotation = rotation_strategy

            if rotation_fallback:
                result.agents_fallback.append("content-rotation-architect")
                print(f"  [AGENT MODE] content-rotation-architect: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("content-rotation-architect")
                print(f"  [AGENT MODE] content-rotation-architect: invoked successfully", file=sys.stderr)

            # Invoke pricing strategist for optimized pricing
            pricing_strategy, pricing_fallback = agent_invoker.invoke_pricing_strategist(agent_context)
            agent_context.pricing = pricing_strategy

            if pricing_fallback:
                result.agents_fallback.append("pricing-strategist")
                print(f"  [AGENT MODE] pricing-strategist: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("pricing-strategist")
                print(f"  [AGENT MODE] pricing-strategist: invoked successfully", file=sys.stderr)

        except Exception as e:
            print(f"  [AGENT MODE] Warning: Content strategy agents failed: {e}", file=sys.stderr)
            result.agents_fallback.extend(["content-rotation-architect", "pricing-strategist"])

    # Step 2B: Load additional content types (if enabled)
    wall_captions = []
    previews = []
    polls_pool = []
    wheel_config = None

    if CONTENT_TYPE_LOADERS_AVAILABLE:
        if getattr(config, 'enable_wall_posts', False):
            wall_captions = load_wall_post_captions(conn, config.creator_id)

        if getattr(config, 'enable_free_previews', False):
            previews = load_free_previews(conn, config.creator_id)

        if getattr(config, 'enable_polls', False):
            polls_pool = load_polls(conn, config.creator_id)

        if getattr(config, 'enable_game_wheel', False):
            wheel_config = load_game_wheel_config(conn, config.creator_id)

    # Step 3B: Apply persona scores to new content types
    if CONTENT_TYPE_LOADERS_AVAILABLE:
        if previews:
            previews = apply_preview_persona_scores(previews, profile)
        if polls_pool:
            polls_pool = apply_poll_persona_scores(polls_pool, profile)

    # NEW Step 4: QUALITY SCORING (full mode only)
    # Prepare caption pool (max 60 for LLM evaluation to control costs)
    caption_pool = captions[:60]
    quality_scores: dict = {}

    if config.mode == "full" and config.use_quality_scoring:
        if QUALITY_SCORING_AVAILABLE:
            print(f"  [FULL MODE] Step 4: Quality scoring {len(caption_pool)} captions...", file=sys.stderr)

            # Import CreatorProfile from quality_scoring module
            from quality_scoring import CreatorProfile as QSCreatorProfile

            scorer = QualityScorer(conn)
            quality_scores = scorer.score_caption_batch(
                [{"caption_id": c.caption_id, "caption_text": c.caption_text} for c in caption_pool],
                QSCreatorProfile(
                    creator_id=profile.creator_id,
                    page_name=profile.page_name,
                    primary_tone=profile.primary_tone,
                    emoji_frequency=profile.emoji_frequency,
                    slang_level=profile.slang_level,
                )
            )

            # Filter out poor quality captions (overall_score < 0.30)
            caption_pool_filtered = scorer.filter_by_quality(
                [asdict(c) for c in caption_pool],
                quality_scores,
                min_score=0.30
            )

            # Convert back to Caption objects
            caption_pool = [
                Caption(**{k: v for k, v in c.items() if k in Caption.__dataclass_fields__})
                for c in caption_pool_filtered
            ]

            print(f"  [FULL MODE] Quality scoring complete: {len(caption_pool)} captions passed", file=sys.stderr)
        else:
            print("  [FULL MODE] Warning: QualityScorer not available, skipping quality scoring", file=sys.stderr)

    # Apply quality-enhanced weights if available
    if quality_scores:
        for caption in caption_pool:
            if caption.caption_id in quality_scores:
                qs = quality_scores[caption.caption_id]
                # New weight formula: (perf * 0.4 + fresh * 0.2 + quality * 0.4) * persona_boost
                quality_mod = get_quality_modifier(qs.classification)
                caption.final_weight = calculate_enhanced_weight(
                    caption.performance_score,
                    caption.freshness_score,
                    qs.overall_score,
                    caption.persona_boost,
                    quality_mod
                )
    else:
        # Use original captions if no quality scoring
        caption_pool = captions

    # Step 5: BUILD STRUCTURE - Create weekly slots
    slots = build_weekly_slots(config, profile.best_hours)

    # Count PPV slots for allocation calculation
    ppv_slots = [s for s in slots if s.get("type") == "ppv"]
    total_ppv_slots = len(ppv_slots)
    logger.info(f"[Step 5] Built {total_ppv_slots} PPV slots for the week")

    # NEW: Calculate content type slot allocation based on earnings weights
    content_type_allocation = calculate_content_type_slot_allocation(
        conn, config.creator_id, total_ppv_slots
    )
    logger.info(f"[Step 5] Content type slot allocation: {content_type_allocation}")

    # Log allocation details
    for ct_name, slot_count in content_type_allocation.items():
        pct = (slot_count / total_ppv_slots * 100) if total_ppv_slots > 0 else 0
        logger.info(f"  {ct_name}: {slot_count} slots ({pct:.1f}%)")

    # Step 6: ASSIGN CAPTIONS - Pool-based weighted selection
    # Use new pool-based assignment with stratified pools
    items = assign_captions_to_slots(
        slots=slots,
        captions=caption_pool,
        config=config,
        pools=stratified_pools,
        persona=persona_dict,
        content_type_allocation=content_type_allocation,
    )
    logger.info(f"[Step 6] Assigned {len(items)} PPV items using pool-based selection")

    # Step 6B: Assign wall posts (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and wall_captions:
        wall_items = select_wall_posts_for_slots(
            wall_captions,
            [s for s in slots if s.get("type") == "wall_post"],
            config,
            profile,
            start_item_id=max((i.item_id for i in items), default=0) + 100
        )
        items.extend(wall_items)

    # Step 6C: Assign free previews (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and previews:
        ppv_items = [i for i in items if i.item_type == "ppv"]
        preview_items = select_previews_for_ppvs(
            previews,
            ppv_items,
            config,
            start_item_id=max((i.item_id for i in items), default=0) + 200
        )
        items.extend(preview_items)

    # Step 6D: Assign polls (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and polls_pool:
        poll_items = select_polls_for_week(
            polls_pool,
            config,
            profile,
            config.week_start.isoformat(),
            start_item_id=max((i.item_id for i in items), default=0) + 300
        )
        items.extend(poll_items)

    # Step 6E: Add game wheel (if enabled)
    if CONTENT_TYPE_SCHEDULERS_AVAILABLE and wheel_config:
        wheel_item = create_game_wheel_schedule_item(
            wheel_config,
            config,
            config.week_start.isoformat(),
            item_id=max((i.item_id for i in items), default=0) + 400
        )
        if wheel_item:
            items.append(wheel_item)

    # NEW Step 7: CAPTION ENHANCEMENT (full mode only)
    if config.mode == "full" and config.use_caption_enhancement:
        if CAPTION_ENHANCER_AVAILABLE:
            print(f"  [FULL MODE] Step 7: Enhancing {len(items)} captions...", file=sys.stderr)
            enhancer = CaptionEnhancer(CEPersonaContext(
                creator_id=profile.creator_id,
                page_name=profile.page_name,
                primary_tone=profile.primary_tone,
                emoji_frequency=profile.emoji_frequency,
                slang_level=profile.slang_level,
            ))

            enhanced_count = 0
            for item in items:
                if item.item_type == "ppv" and item.caption_text:
                    enhancement_result = enhancer.enhance_with_rollback(
                        item.caption_id or 0,
                        item.caption_text
                    )
                    if not enhancement_result.used_original:
                        item.caption_text = enhancement_result.enhanced_text
                        tweaks_str = ", ".join(enhancement_result.tweaks_applied[:3])
                        item.notes += f" | Enhanced: {tweaks_str}"
                        enhanced_count += 1

            print(f"  [FULL MODE] Caption enhancement complete: {enhanced_count} enhanced", file=sys.stderr)
        else:
            print("  [FULL MODE] Warning: CaptionEnhancer not available, skipping enhancement", file=sys.stderr)

    # Step 8: GENERATE FOLLOW-UPS (context-aware in full mode)
    if config.enable_follow_ups:
        if config.mode == "full" and config.use_context_followups:
            print(f"  [FULL MODE] Step 8: Generating context-aware follow-ups...", file=sys.stderr)
            items = generate_contextual_follow_ups(items, config, profile)
        else:
            items = generate_follow_ups(items, config)

    # =========================================================================
    # AGENT STEP 8A: MULTI-TOUCH SEQUENCER (After Step 8)
    # Agent: multi-touch-sequencer - Optimizes follow-up timing and messaging
    # =========================================================================
    if agent_invoker and agent_context and config.enable_follow_ups:
        try:
            print(f"  [AGENT MODE] Invoking multi-touch-sequencer...", file=sys.stderr)

            # Get all PPV items that have follow-ups
            ppv_items = [item for item in items if item.item_type == "ppv"]

            for ppv_item in ppv_items:
                followup_sequence, followup_fallback = agent_invoker.invoke_multi_touch_sequencer(
                    agent_context,
                    ppv_item_id=ppv_item.item_id,
                    content_type=ppv_item.content_type_name or "solo"
                )
                agent_context.followup_sequences.append(followup_sequence)

            if followup_fallback:
                if "multi-touch-sequencer" not in result.agents_fallback:
                    result.agents_fallback.append("multi-touch-sequencer")
                    print(f"  [AGENT MODE] multi-touch-sequencer: using fallback", file=sys.stderr)
            else:
                if "multi-touch-sequencer" not in result.agents_used:
                    result.agents_used.append("multi-touch-sequencer")
                    print(f"  [AGENT MODE] multi-touch-sequencer: invoked successfully", file=sys.stderr)

        except Exception as e:
            print(f"  [AGENT MODE] Warning: Multi-touch sequencer failed: {e}", file=sys.stderr)
            if "multi-touch-sequencer" not in result.agents_fallback:
                result.agents_fallback.append("multi-touch-sequencer")

    # Step 9: APPLY DRIP WINDOWS
    items = apply_drip_windows(items, config)

    # Step 10: APPLY PAGE TYPE RULES
    items = apply_page_type_rules(items, config)

    # Step 10B: APPLY CONTENT NOTES PRICE MODIFIERS
    if profile.price_modifiers:
        for item in items:
            if item.item_type == "ppv" and item.suggested_price:
                content_type = item.content_type_name
                if content_type in profile.price_modifiers:
                    item.suggested_price = round(
                        item.suggested_price * profile.price_modifiers[content_type], 2
                    )
                elif None in profile.price_modifiers:
                    item.suggested_price = round(
                        item.suggested_price * profile.price_modifiers[None], 2
                    )

    # =========================================================================
    # AGENT STEP 10A: VALIDATION GUARDIAN (Before Step 11)
    # Agent: validation-guardian - Enhanced validation with auto-fix suggestions
    # =========================================================================
    if agent_invoker and agent_context:
        try:
            print(f"  [AGENT MODE] Invoking validation-guardian...", file=sys.stderr)

            # Convert items to dict format for validation
            schedule_items_dict = [
                {
                    "item_id": item.item_id,
                    "scheduled_date": item.scheduled_date,
                    "scheduled_time": item.scheduled_time,
                    "item_type": item.item_type,
                    "caption_id": item.caption_id,
                    "content_type_name": item.content_type_name,
                    "freshness_score": item.freshness_score,
                    "suggested_price": item.suggested_price,
                }
                for item in items
            ]

            validation_result, validation_fallback = agent_invoker.invoke_validation_guardian(
                agent_context,
                schedule_items_dict
            )
            agent_context.validation_result = validation_result

            if validation_fallback:
                result.agents_fallback.append("validation-guardian")
                print(f"  [AGENT MODE] validation-guardian: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("validation-guardian")
                print(f"  [AGENT MODE] validation-guardian: invoked successfully", file=sys.stderr)

            # Invoke revenue forecaster for projections
            revenue_projection, revenue_fallback = agent_invoker.invoke_revenue_forecaster(agent_context)
            agent_context.revenue_projection = revenue_projection

            if revenue_fallback:
                result.agents_fallback.append("revenue-forecaster")
                print(f"  [AGENT MODE] revenue-forecaster: using fallback", file=sys.stderr)
            else:
                result.agents_used.append("revenue-forecaster")
                print(f"  [AGENT MODE] revenue-forecaster: invoked successfully", file=sys.stderr)

        except Exception as e:
            print(f"  [AGENT MODE] Warning: Validation/forecasting agents failed: {e}", file=sys.stderr)
            result.agents_fallback.extend(["validation-guardian", "revenue-forecaster"])

    # Step 11: VALIDATE
    validation_issues = validate_schedule(items, config)
    result.validation_issues = validation_issues
    result.validation_passed = not any(
        issue.severity == "error" for issue in validation_issues
    )

    # Step 12: Populate result
    result.items = items
    result.total_ppvs = sum(1 for item in items if item.item_type == "ppv")
    result.total_bumps = sum(1 for item in items if item.item_type == "bump")
    result.total_follow_ups = sum(1 for item in items if item.is_follow_up)
    result.total_drip = sum(1 for item in items if item.item_type == "drip")
    result.unique_captions = len(set(item.caption_id for item in items if item.caption_id))

    ppv_items = [item for item in items if item.item_type == "ppv"]
    if ppv_items:
        result.avg_freshness = sum(item.freshness_score for item in ppv_items) / len(ppv_items)
        result.avg_performance = sum(item.performance_score for item in ppv_items) / len(ppv_items)

    # Update result counts for new content types
    result.total_wall_posts = sum(1 for i in items if i.item_type == "wall_post")
    result.total_free_previews = sum(1 for i in items if i.item_type == "free_preview")
    result.total_polls = sum(1 for i in items if i.item_type == "poll")
    result.total_game_wheels = sum(1 for i in items if i.item_type == "game_wheel")

    # =========================================================================
    # AGENT STEP FINAL: Update agent mode status and log summary
    # =========================================================================
    if config.use_agents:
        total_agents_attempted = len(result.agents_used) + len(result.agents_fallback)
        agents_successful = len(result.agents_used)

        if agents_successful == 0 and total_agents_attempted > 0:
            result.agent_mode = "disabled"  # All agents failed
        elif agents_successful < total_agents_attempted:
            result.agent_mode = "partial"  # Some agents used fallback
        elif agents_successful > 0:
            result.agent_mode = "enabled"  # All agents succeeded

        print(f"  [AGENT MODE] Summary: {agents_successful}/{total_agents_attempted} agents invoked successfully", file=sys.stderr)
        if result.agents_used:
            print(f"  [AGENT MODE] Agents used: {', '.join(result.agents_used)}", file=sys.stderr)
        if result.agents_fallback:
            print(f"  [AGENT MODE] Fallbacks used: {', '.join(result.agents_fallback)}", file=sys.stderr)

    return result


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def format_markdown(result: ScheduleResult) -> str:
    """Format schedule result as professional Markdown."""
    # Build mode indicator string
    mode_indicator = f"Mode: {result.agent_mode.upper()}"
    if result.agent_mode == "enabled":
        mode_indicator = f"Mode: Agent-Assisted ({len(result.agents_used)}/{len(result.agents_used) + len(result.agents_fallback)} agents invoked)"
    elif result.agent_mode == "partial":
        mode_indicator = f"Mode: Agent-Assisted (Partial - {len(result.agents_used)}/{len(result.agents_used) + len(result.agents_fallback)} agents invoked)"

    lines = [
        f"# Weekly Schedule: {result.display_name}",
        f"## Week: {result.week_start} - {result.week_end}",
        f"## Volume: {result.volume_level} | Page Type: {result.page_type} | {mode_indicator}",
        "",
        "---",
        "",
        "### Creator Intelligence Brief",
        "",
        f"- **Active Fans**: (see profile)",
        f"- **Best Hours**: {', '.join(f'{h:02d}:00' for h in result.best_hours[:5])}",
        f"- **Vault Types**: {', '.join(result.vault_types[:8]) if result.vault_types else 'N/A'}",
        "",
    ]

    # Add agent summary section if agents were used
    if result.agents_used or result.agents_fallback:
        lines.append("### Agent System Status")
        lines.append("")
        if result.agents_used:
            lines.append(f"- **Agents Invoked**: {', '.join(result.agents_used)}")
        if result.agents_fallback:
            lines.append(f"- **Fallbacks Used**: {', '.join(result.agents_fallback)}")
        lines.append("")

    # NEW: Content Mix Summary
    lines.append("### Content Mix Summary")
    lines.append("")
    lines.append("| Type | Count | Notes |")
    lines.append("|------|-------|-------|")
    lines.append(f"| PPV | {result.total_ppvs} | Core revenue |")
    lines.append(f"| Follow-ups | {result.total_follow_ups} | Bump messages |")
    if result.total_wall_posts > 0:
        lines.append(f"| Wall Posts | {result.total_wall_posts} | Feed engagement |")
    if result.total_free_previews > 0:
        lines.append(f"| Free Previews | {result.total_free_previews} | PPV teasers |")
    if result.total_polls > 0:
        lines.append(f"| Polls | {result.total_polls} | Interactive |")
    if result.total_game_wheels > 0:
        lines.append(f"| Game Wheel | {result.total_game_wheels} | Gamification |")
    lines.append("")

    lines.extend([
        "---",
        ""
    ])

    # Group items by date
    items_by_date: dict[str, list[ScheduleItem]] = {}
    for item in result.items:
        if item.scheduled_date not in items_by_date:
            items_by_date[item.scheduled_date] = []
        items_by_date[item.scheduled_date].append(item)

    # Daily schedules
    for date_str in sorted(items_by_date.keys()):
        day_items = items_by_date[date_str]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = dt.strftime("%A")

        lines.append(f"### {day_name} {date_str}")
        lines.append("")
        lines.append("| Time | Type | Content | Caption | Price | Score | Fresh |")
        lines.append("|------|------|---------|---------|-------|-------|-------|")

        ppv_count = 0
        bump_count = 0
        day_projected = 0.0

        for item in sorted(day_items, key=lambda x: x.scheduled_time):
            if item.item_type == "ppv":
                ppv_count += 1
                caption_preview = item.caption_text or "-"
                caption_preview = caption_preview.replace("|", "/").replace("\n", " ")
                price_str = f"${item.suggested_price:.2f}" if item.suggested_price else "-"
                day_projected += (item.suggested_price or 0) * 0.05  # Estimate 5% conversion

                lines.append(
                    f"| {item.scheduled_time} | PPV | {item.content_type_name or 'N/A'} | "
                    f"{caption_preview} | {price_str} | {item.performance_score:.0f} | {item.freshness_score:.0f} |"
                )
            elif item.item_type == "bump":
                bump_count += 1
                lines.append(
                    f"| {item.scheduled_time} | Bump | - | {item.caption_text or '(follow-up)'} | - | - | - |"
                )
            elif item.item_type == "drip":
                lines.append(
                    f"| {item.scheduled_time} | Drip | - | [DRIP WINDOW] | - | - | - |"
                )
            elif item.item_type == "wall_post":
                caption_preview = item.caption_text or "-"
                caption_preview = caption_preview.replace("|", "/").replace("\n", " ")
                lines.append(
                    f"| {item.scheduled_time} | Wall | {item.content_type_name or 'N/A'} | "
                    f"{caption_preview} | - | - | - |"
                )
            elif item.item_type == "free_preview":
                caption_preview = item.caption_text or "-"
                caption_preview = caption_preview.replace("|", "/").replace("\n", " ")
                preview_note = f"Pre #{item.linked_ppv_id}" if item.linked_ppv_id else item.preview_type or "preview"
                lines.append(
                    f"| {item.scheduled_time} | Preview | {preview_note} | "
                    f"{caption_preview} | - | - | - |"
                )
            elif item.item_type == "poll":
                question_preview = item.caption_text or "-"
                question_preview = question_preview.replace("|", "/").replace("\n", " ")
                options_count = len(item.poll_options) if item.poll_options else 2
                duration = item.poll_duration_hours or 24
                lines.append(
                    f"| {item.scheduled_time} | Poll | {options_count} options | "
                    f"{question_preview} | - | - | {duration}h |"
                )
            elif item.item_type == "game_wheel":
                lines.append(
                    f"| {item.scheduled_time} | Wheel | Promo | "
                    f"{item.caption_text or 'Spin to win!'} | - | - | - |"
                )

        lines.append("")
        lines.append(f"**Daily Summary**: {ppv_count} PPVs | {bump_count} Bumps | Projected: ${day_projected:.2f}")
        lines.append("")

    # Weekly summary
    lines.extend([
        "---",
        "",
        "### Weekly Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total PPVs | {result.total_ppvs} |",
        f"| Total Bumps | {result.total_bumps} |",
        f"| Total Follow-ups | {result.total_follow_ups} |",
        f"| Total Wall Posts | {result.total_wall_posts} |",
        f"| Total Previews | {result.total_free_previews} |",
        f"| Total Polls | {result.total_polls} |",
        f"| Unique Captions | {result.unique_captions} |",
        f"| Avg Caption Score | {result.avg_performance:.1f} |",
        f"| Avg Freshness | {result.avg_freshness:.1f} |",
        ""
    ])

    # Validation status
    lines.extend([
        "### Validation Status",
        ""
    ])

    # Check each rule
    error_rules = set(i.rule_name for i in result.validation_issues if i.severity == "error")
    warning_rules = set(i.rule_name for i in result.validation_issues if i.severity == "warning")

    checks = [
        ("ppv_spacing", "PPV Spacing (>= 3h)"),
        ("duplicate_captions", "No Duplicate Captions"),
        ("freshness_threshold", "Freshness Compliance (>= 30)"),
        ("content_rotation", "Content Rotation"),
        ("followup_timing", "Follow-up Timing (15-45 min)"),
    ]

    for rule, label in checks:
        if rule in error_rules:
            lines.append(f"- FAILED: {label}")
        elif rule in warning_rules:
            lines.append(f"- WARNING: {label}")
        else:
            lines.append(f"- PASSED: {label}")

    lines.append("")

    if result.validation_issues:
        lines.append("### Issues Found")
        lines.append("")
        for issue in result.validation_issues:
            severity_marker = "[ERROR]" if issue.severity == "error" else "[WARN]"
            lines.append(f"- {severity_marker} **{issue.rule_name}**: {issue.message}")
        lines.append("")

    lines.extend([
        "---",
        f"Generated: {result.generated_at} | Schedule ID: {result.schedule_id}",
        ""
    ])

    return "\n".join(lines)


def format_json(result: ScheduleResult) -> str:
    """Format schedule result as JSON."""
    data = {
        "schedule_id": result.schedule_id,
        "creator_id": result.creator_id,
        "creator_name": result.creator_name,
        "display_name": result.display_name,
        "page_type": result.page_type,
        "week_start": result.week_start,
        "week_end": result.week_end,
        "volume_level": result.volume_level,
        "summary": {
            "total_ppvs": result.total_ppvs,
            "total_bumps": result.total_bumps,
            "total_follow_ups": result.total_follow_ups,
            "unique_captions": result.unique_captions,
            "avg_freshness": round(result.avg_freshness, 2),
            "avg_performance": round(result.avg_performance, 2),
            # Extended content type counts
            "total_wall_posts": result.total_wall_posts,
            "total_free_previews": result.total_free_previews,
            "total_polls": result.total_polls,
            "total_game_wheels": result.total_game_wheels
        },
        # Agent system integration (Phase 3)
        "agent_system": {
            "mode": result.agent_mode,
            "agents_used": result.agents_used,
            "agents_fallback": result.agents_fallback,
            "total_invoked": len(result.agents_used),
            "total_fallback": len(result.agents_fallback)
        },
        "validation": {
            "passed": result.validation_passed,
            "issues": [
                {
                    "rule_name": issue.rule_name,
                    "severity": issue.severity,
                    "message": issue.message,
                    "item_ids": issue.item_ids
                }
                for issue in result.validation_issues
            ]
        },
        "best_hours": result.best_hours,
        "vault_types": result.vault_types,
        "items": [asdict(item) for item in result.items],
        "generated_at": result.generated_at
    }
    return json.dumps(data, indent=2)


# ============================================================================
# BATCH MODE
# ============================================================================

def generate_batch_schedules(
    conn: sqlite3.Connection,
    week_start: date,
    week_end: date,
    output_dir: Path | None = None
) -> list[ScheduleResult]:
    """Generate schedules for all active creators."""
    cursor = conn.execute(
        "SELECT creator_id, page_name, page_type, current_active_fans FROM creators WHERE is_active = 1"
    )
    creators = cursor.fetchall()

    results = []
    total = len(creators)

    # Create optimizer instance for batch processing
    optimizer = MultiFactorVolumeOptimizer(conn)

    for i, creator in enumerate(creators, 1):
        page_name = creator["page_name"]
        print(f"[{i}/{total}] Generating schedule for {page_name}...", file=sys.stderr)

        # Use multi-factor volume optimization
        try:
            strategy = optimizer.calculate_optimal_volume(
                creator["creator_id"],
                creator["current_active_fans"]
            )
            volume_level = strategy.volume_level
            ppv_per_day = strategy.ppv_per_day
            bump_per_day = strategy.bump_per_day
            is_paid_page = strategy.page_type == "paid"
            volume_period = "week" if is_paid_page else "day"
            ppv_per_week = strategy.ppv_per_week
        except Exception as e:
            print(f"    Warning: Volume optimization failed, using fallback: {e}", file=sys.stderr)
            volume_level, ppv_per_day, bump_per_day = get_volume_level(
                creator["current_active_fans"] or 0
            )
            strategy = None
            is_paid_page = (creator["page_type"] or "paid") == "paid"
            volume_period = "day"
            ppv_per_week = ppv_per_day * 7

        config = ScheduleConfig(
            creator_id=creator["creator_id"],
            creator_name=creator["page_name"],
            page_type=creator["page_type"] or "paid",
            week_start=week_start,
            week_end=week_end,
            volume_level=volume_level,
            ppv_per_day=ppv_per_day,
            bump_per_day=bump_per_day,
            enable_follow_ups=True,
            # Volume optimization fields
            volume_period=volume_period,
            ppv_per_week=ppv_per_week,
            is_paid_page=is_paid_page,
            volume_strategy=strategy
        )

        result = generate_schedule(config, conn)
        results.append(result)

        # Save individual file if output_dir specified
        if output_dir:
            # Sanitize creator name for safe filesystem usage
            safe_page_name = re.sub(r'[^\w\-_]', '_', page_name)
            creator_dir = output_dir / safe_page_name
            try:
                creator_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                print(f"    Error: Cannot create {creator_dir}: {e}", file=sys.stderr)
                continue
            week_str = format_week_string(week_start)
            output_file = creator_dir / f"{week_str}.md"
            output_file.write_text(format_markdown(result))
            print(f"    Saved to {output_file}", file=sys.stderr)

    return results


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate optimized weekly content schedules for OnlyFans creators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_schedule.py --creator missalexa --week 2025-W01
    python generate_schedule.py --creator-id abc123 --week 2025-W01 --output schedule.md
    python generate_schedule.py --batch --week 2025-W01 --output-dir schedules/

Business Rules Enforced:
    - PPV Spacing: MINIMUM 3 hours between PPV messages
    - Follow-ups: 15-45 minutes after each PPV
    - Freshness: ALL captions must have freshness >= 30
    - Rotation: NEVER same content type consecutively
        """
    )

    parser.add_argument(
        "--creator", "-c",
        help="Creator page name (e.g., missalexa)"
    )
    parser.add_argument(
        "--creator-id",
        help="Creator UUID"
    )
    parser.add_argument(
        "--week", "-w",
        required=True,
        help="Week in ISO format (YYYY-Www, e.g., 2025-W01)"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Generate schedules for all active creators"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for batch mode"
    )
    parser.add_argument(
        "--stdout", "--print",
        action="store_true",
        dest="stdout",
        help="Print to console instead of auto-saving to file"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--no-follow-ups",
        action="store_true",
        help="Disable follow-up bump generation"
    )
    parser.add_argument(
        "--enable-drip",
        action="store_true",
        help="Enable drip window enforcement"
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"Database path (default: {DB_PATH})"
    )
    # Enhanced pipeline mode arguments (Phase 4)
    parser.add_argument(
        "--mode", "-m",
        choices=["quick", "full"],
        default="quick",
        help="Generation mode: quick (pattern-only) or full (with LLM)"
    )
    parser.add_argument(
        "--enable-quality-scoring",
        action="store_true",
        help="Enable LLM-based quality scoring (full mode)"
    )
    parser.add_argument(
        "--enable-enhancement",
        action="store_true",
        help="Enable caption enhancement (full mode)"
    )
    parser.add_argument(
        "--enable-context-followups",
        action="store_true",
        help="Enable context-aware follow-ups (full mode)"
    )
    parser.add_argument(
        "--use-agents",
        action="store_true",
        help="Enable sub-agent delegation for enhanced optimization (pricing, timing, rotation, validation)"
    )
    # NEW: Content type enablement flags
    parser.add_argument(
        "--enable-wall-posts",
        action="store_true",
        help="Include wall posts in schedule (feed engagement)"
    )
    parser.add_argument(
        "--wall-posts-per-day",
        type=int,
        default=2,
        help="Number of wall posts per day (default: 2)"
    )
    parser.add_argument(
        "--enable-previews",
        action="store_true",
        help="Include free previews before high-value PPVs"
    )
    parser.add_argument(
        "--enable-polls",
        action="store_true",
        help="Include interactive polls in schedule"
    )
    parser.add_argument(
        "--polls-per-week",
        type=int,
        default=3,
        help="Number of polls per week (default: 3)"
    )
    parser.add_argument(
        "--enable-game-wheel",
        action="store_true",
        help="Include game wheel promotion in schedule"
    )

    args = parser.parse_args()

    if not args.batch and not args.creator and not args.creator_id:
        parser.error("Must specify --creator, --creator-id, or --batch")

    # Parse week
    try:
        week_start, week_end = parse_iso_week(args.week)
    except Exception as e:
        parser.error(f"Invalid week format: {e}")

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        if args.batch:
            # Generate for all active creators
            # Default to auto-save unless --stdout is specified
            if args.output_dir:
                output_dir = Path(args.output_dir)
            elif not args.stdout:
                output_dir = DEFAULT_SCHEDULES_DIR
            else:
                output_dir = None

            results = generate_batch_schedules(conn, week_start, week_end, output_dir)

            if not output_dir:
                if args.format == "json":
                    output = json.dumps(
                        [json.loads(format_json(r)) for r in results],
                        indent=2
                    )
                else:
                    output = "\n\n---\n\n".join(format_markdown(r) for r in results)

                if args.output:
                    Path(args.output).write_text(output)
                    print(f"Batch schedule written to {args.output}")
                else:
                    print(output)

            # Summary
            passed = sum(1 for r in results if r.validation_passed)
            print(f"\nBatch complete: {passed}/{len(results)} schedules passed validation", file=sys.stderr)

        else:
            # Generate for single creator
            profile = load_creator_profile(
                conn,
                creator_name=args.creator,
                creator_id=args.creator_id
            )

            if not profile:
                print("Error: Creator not found", file=sys.stderr)
                sys.exit(1)

            # Use multi-factor volume optimization
            optimizer = MultiFactorVolumeOptimizer(conn)
            try:
                strategy = optimizer.calculate_optimal_volume(
                    profile.creator_id,
                    profile.active_fans
                )
                volume_level = strategy.volume_level
                ppv_per_day = strategy.ppv_per_day
                bump_per_day = strategy.bump_per_day
                is_paid_page = strategy.page_type == "paid"
                volume_period = "week" if is_paid_page else "day"
                ppv_per_week = strategy.ppv_per_week
            except Exception as e:
                print(f"Warning: Volume optimization failed, using fallback: {e}", file=sys.stderr)
                volume_level, ppv_per_day, bump_per_day = get_volume_level(profile.active_fans)
                strategy = None
                is_paid_page = profile.page_type == "paid"
                volume_period = "day"
                ppv_per_week = ppv_per_day * 7

            # Determine enhanced mode settings
            # In full mode, enable all LLM features unless explicitly disabled
            is_full_mode = args.mode == "full"
            use_quality = args.enable_quality_scoring or is_full_mode
            use_enhancement = args.enable_enhancement or is_full_mode
            use_context_followups = args.enable_context_followups or is_full_mode

            config = ScheduleConfig(
                creator_id=profile.creator_id,
                creator_name=profile.page_name,
                page_type=profile.page_type,
                week_start=week_start,
                week_end=week_end,
                volume_level=volume_level,
                ppv_per_day=ppv_per_day,
                bump_per_day=bump_per_day,
                enable_follow_ups=not args.no_follow_ups,
                enable_drip_windows=args.enable_drip,
                # Volume optimization fields
                volume_period=volume_period,
                ppv_per_week=ppv_per_week,
                is_paid_page=is_paid_page,
                volume_strategy=strategy,
                # Enhanced pipeline mode fields (Phase 4)
                mode=args.mode,
                use_quality_scoring=use_quality,
                use_caption_enhancement=use_enhancement,
                use_context_followups=use_context_followups,
                # Sub-agent integration
                use_agents=args.use_agents,
                # NEW: Content type flags from CLI
                enable_wall_posts=args.enable_wall_posts,
                wall_posts_per_day=args.wall_posts_per_day,
                enable_free_previews=args.enable_previews,
                enable_polls=args.enable_polls,
                polls_per_week=args.polls_per_week,
                enable_game_wheel=args.enable_game_wheel,
            )

            # Display mode information
            if is_full_mode:
                print(f"[FULL MODE] Quality scoring: {use_quality}", file=sys.stderr)
                print(f"[FULL MODE] Caption enhancement: {use_enhancement}", file=sys.stderr)
                print(f"[FULL MODE] Context follow-ups: {use_context_followups}", file=sys.stderr)

            result = generate_schedule(config, conn)

            if args.format == "json":
                output = format_json(result)
                ext = ".json"
            else:
                output = format_markdown(result)
                ext = ".md"

            if args.output:
                # Explicit output path
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output)
                print(f"Schedule saved to {output_path}", file=sys.stderr)
            elif args.stdout:
                # Explicit stdout request
                print(output)
            else:
                # Default: auto-save to standard location
                week_str = format_week_string(week_start)
                # Sanitize creator name for safe filesystem usage
                safe_creator_name = re.sub(r'[^\w\-_]', '_', config.creator_name)
                creator_dir = DEFAULT_SCHEDULES_DIR / safe_creator_name
                try:
                    creator_dir.mkdir(parents=True, exist_ok=True)
                except PermissionError as e:
                    print(f"Error: Cannot create output directory {creator_dir}: {e}", file=sys.stderr)
                    print("Use --stdout to print to console, or set EROS_SCHEDULES_PATH to a writable location.", file=sys.stderr)
                    sys.exit(1)
                output_path = creator_dir / f"{week_str}{ext}"
                output_path.write_text(output)
                print(f"Schedule saved to {output_path}", file=sys.stderr)

            # Exit code based on validation
            if not result.validation_passed:
                print(f"\nWarning: Schedule has validation errors", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
