#!/usr/bin/env python3
"""
Content Type Loaders - Load various content types for scheduling.

This module provides loading functions for:
- Wall/Feed posts (captions marked as wall-eligible)
- Free previews (teaser content)
- Polls (interactive engagement)
- Game wheel configurations (gamification)
- Tier 3 Engagement: DM farm, like farm, text-only bumps, wall link drops
- Tier 4 Retention: Renew-on posts/MM, expired subscriber win-back, game posts

All functions accept a SQLite connection and creator_id,
returning typed data class instances from generate_schedule.

Note: Uses lazy imports to avoid circular import issues with generate_schedule.
"""

from __future__ import annotations

import functools
import sqlite3
from typing import TYPE_CHECKING, Any, Callable, TypeVar

# Type hints only - these won't cause circular imports
if TYPE_CHECKING:
    from generate_schedule import (
        Caption,
        CreatorProfile,
        FreePreview,
        GameWheelConfig,
        Poll,
    )

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def _get_caption_class():
    """Lazy import Caption class to avoid circular imports."""
    from generate_schedule import Caption

    return Caption


def _get_free_preview_class():
    """Lazy import FreePreview class to avoid circular imports."""
    from generate_schedule import FreePreview

    return FreePreview


def _get_poll_class():
    """Lazy import Poll class to avoid circular imports."""
    from generate_schedule import Poll

    return Poll


def _get_game_wheel_config_class():
    """Lazy import GameWheelConfig class to avoid circular imports."""
    from generate_schedule import GameWheelConfig

    return GameWheelConfig


# =============================================================================
# PAGE TYPE GUARD DECORATOR
# =============================================================================


def paid_page_only(func: F) -> F:
    """
    Decorator to enforce paid-page-only content types.

    Wraps loader functions that should only return content for paid pages.
    For free pages, returns an empty list immediately without querying the database.

    Args:
        func: Loader function with signature (conn, creator_id, page_type, persona)

    Returns:
        Wrapped function that returns [] for free pages

    Example:
        @paid_page_only
        def load_vip_posts(conn, creator_id, page_type, persona):
            ...
    """

    @functools.wraps(func)
    def wrapper(
        conn: sqlite3.Connection, creator_id: str, page_type: str, persona: dict
    ) -> list[dict]:
        if page_type.lower() != "paid":
            return []
        return func(conn, creator_id, page_type, persona)

    return wrapper  # type: ignore[return-value]


# =============================================================================
# ENGAGEMENT CONTENT DATA CLASS
# =============================================================================


def _create_engagement_content(
    content_id: int | None,
    content_text: str | None,
    content_type: str,
    has_caption: bool = True,
    theme_guidance: str = "",
    freshness_score: float = 100.0,
    performance_score: float = 50.0,
    persona_boost: float = 1.0,
    requires_flyer: bool = False,
    channel: str = "mass_message",
    tone: str | None = None,
    extra_data: dict | None = None,
) -> dict:
    """
    Create a standardized engagement content dictionary.

    This factory function creates content dictionaries that can be used by
    the schedule generator for any content type (engagement, retention, etc.).

    Args:
        content_id: Unique identifier for the content
        content_text: The text content or caption
        content_type: Type identifier (e.g., "dm_farm", "renew_on_mm")
        has_caption: Whether real caption text exists
        theme_guidance: Guidance text for slots without captions
        freshness_score: Content freshness (0-100)
        performance_score: Historical performance (0-100)
        persona_boost: Persona matching multiplier (1.0-1.4)
        requires_flyer: Whether content needs attached media
        channel: Distribution channel
        tone: Content tone for persona matching
        extra_data: Additional type-specific data

    Returns:
        Standardized content dictionary
    """
    result = {
        "content_id": content_id,
        "content_text": content_text,
        "content_type": content_type,
        "has_caption": has_caption,
        "theme_guidance": theme_guidance,
        "freshness_score": freshness_score,
        "performance_score": performance_score,
        "persona_boost": persona_boost,
        "requires_flyer": requires_flyer,
        "channel": channel,
        "tone": tone,
    }
    if extra_data:
        result.update(extra_data)
    return result


def _apply_persona_boost(
    content: dict, persona: dict, base_boost: float = 1.0
) -> dict:
    """
    Apply persona boost to content based on tone matching.

    Args:
        content: Content dictionary with 'tone' field
        persona: Creator persona with 'primary_tone' field
        base_boost: Starting boost value

    Returns:
        Content dictionary with updated persona_boost
    """
    boost = base_boost

    content_tone = content.get("tone")
    persona_tone = persona.get("primary_tone")

    if content_tone and persona_tone:
        if content_tone.lower() == persona_tone.lower():
            boost *= 1.15  # 15% boost for exact tone match

    content["persona_boost"] = boost
    return content


# =============================================================================
# THEME GUIDANCE HELPER
# =============================================================================


def get_theme_guidance(content_type: str) -> str:
    """
    Return theme guidance for content types without captions.

    Retrieves theme guidance from the content type registry for use
    when a loader finds no captions in the database.

    Args:
        content_type: The content type ID (e.g., "vip_post", "bundle")

    Returns:
        Theme guidance string, or generic guidance if type not found
    """
    try:
        from content_type_registry import REGISTRY

        type_info = REGISTRY.get(content_type)
        return type_info.theme_guidance
    except (ImportError, KeyError):
        # Fallback guidance if registry not available or type not found
        return f"Create engaging {content_type.replace('_', ' ')} content"


def _create_placeholder_content(
    content_type: str,
    extra_data: dict | None = None,
) -> dict:
    """
    Create a placeholder content dict for content types without captions.

    Used when a loader finds no matching captions in the database.

    Args:
        content_type: The content type ID (e.g., "vip_post", "bundle")
        extra_data: Additional type-specific fields

    Returns:
        Placeholder content dictionary
    """
    result = {
        "content_id": None,
        "content_text": None,
        "content_type": content_type,
        "has_caption": False,
        "theme_guidance": get_theme_guidance(content_type),
        "freshness_score": 100.0,
        "performance_score": 50.0,
        "persona_boost": 1.0,
    }
    if extra_data:
        result.update(extra_data)
    return result


# =============================================================================
# GENERIC PERSONA SCORING
# =============================================================================


def apply_generic_persona_scores(items: list[dict], persona: dict) -> list[dict]:
    """
    Apply persona boost scoring to any content type.

    Provides a unified persona scoring function that works with dictionary-based
    content items. Matches tone, emoji style, and slang level against the
    creator's persona profile.

    Args:
        items: List of content dictionaries with optional tone/emoji/slang fields
        persona: Creator persona dict with primary_tone, emoji_frequency, slang_level

    Returns:
        List of items with persona_boost field updated (1.0 to 1.4x range)

    Example:
        >>> items = [{"content_id": 1, "tone": "playful", "emoji_style": "heavy"}]
        >>> persona = {"primary_tone": "playful", "emoji_frequency": "heavy"}
        >>> scored = apply_generic_persona_scores(items, persona)
        >>> scored[0]["persona_boost"]  # 1.15 * 1.1 = 1.265
    """
    for item in items:
        boost = 1.0

        # Tone matching (15% boost for exact match)
        item_tone = item.get("tone")
        persona_tone = persona.get("primary_tone")
        if item_tone and persona_tone:
            if item_tone.lower() == persona_tone.lower():
                boost *= 1.15

        # Emoji style matching (10% boost)
        item_emoji = item.get("emoji_style")
        persona_emoji = persona.get("emoji_frequency")
        if item_emoji and persona_emoji:
            if item_emoji.lower() == persona_emoji.lower():
                boost *= 1.10

        # Slang level matching (10% boost)
        item_slang = item.get("slang_level")
        persona_slang = persona.get("slang_level")
        if item_slang and persona_slang:
            if item_slang.lower() == persona_slang.lower():
                boost *= 1.10

        # Cap at maximum 1.4x boost
        item["persona_boost"] = min(boost, 1.4)

    return items


# =============================================================================
# WALL POST CAPTIONS
# =============================================================================


def load_wall_post_captions(
    conn: sqlite3.Connection, creator_id: str, min_freshness: float = 30.0
) -> list[Caption]:
    """
    Load captions eligible for wall posts.

    Wall posts use different selection criteria than PPV:
    - Lower minimum freshness (30 vs 40 for PPV)
    - Prefer shorter, hookier captions
    - Include both paid and free eligible

    Args:
        conn: Database connection
        creator_id: Creator UUID
        min_freshness: Minimum freshness score (default: 30.0)

    Returns:
        List of Caption objects marked as wall-eligible
    """
    Caption = _get_caption_class()

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
            cb.is_universal
        FROM caption_bank cb
        LEFT JOIN content_types ct ON cb.content_type_id = ct.content_type_id
        WHERE cb.is_active = 1
          AND cb.is_wall_eligible = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 100
    """
    cursor = conn.execute(query, (creator_id, min_freshness))

    captions = []
    for row in cursor.fetchall():
        captions.append(
            Caption(
                caption_id=row["caption_id"],
                caption_text=row["caption_text"],
                caption_type=row["caption_type"] or "wall",
                content_type_id=row["content_type_id"],
                content_type_name=row["content_type_name"],
                performance_score=row["performance_score"] or 50.0,
                freshness_score=row["freshness_score"] or 100.0,
                tone=row["tone"],
                emoji_style=row["emoji_style"],
                slang_level=row["slang_level"],
                is_universal=bool(row["is_universal"]),
            )
        )

    return captions


# =============================================================================
# FREE PREVIEWS
# =============================================================================


def load_free_previews(
    conn: sqlite3.Connection, creator_id: str, min_freshness: float = 30.0
) -> list[FreePreview]:
    """
    Load available free preview content.

    Free previews are teasers designed to build anticipation for PPV content.
    Types include: teaser, countdown, behind_scenes, censored

    Args:
        conn: Database connection
        creator_id: Creator UUID
        min_freshness: Minimum freshness score (default: 30.0)

    Returns:
        List of FreePreview objects sorted by conversion rate
    """
    FreePreview = _get_free_preview_class()

    query = """
        SELECT
            fp.preview_id,
            fp.preview_text,
            fp.preview_type,
            fp.content_type_id,
            fp.linked_ppv_type,
            fp.tone,
            fp.performance_score,
            fp.freshness_score
        FROM free_preview_bank fp
        WHERE fp.is_active = 1
          AND (fp.creator_id = ? OR fp.is_universal = 1)
          AND fp.freshness_score >= ?
        ORDER BY fp.conversion_rate DESC, fp.freshness_score DESC
        LIMIT 50
    """
    cursor = conn.execute(query, (creator_id, min_freshness))

    previews = []
    for row in cursor.fetchall():
        previews.append(
            FreePreview(
                preview_id=row["preview_id"],
                preview_text=row["preview_text"],
                preview_type=row["preview_type"],
                content_type_id=row["content_type_id"],
                linked_ppv_type=row["linked_ppv_type"],
                tone=row["tone"],
                performance_score=row["performance_score"] or 50.0,
                freshness_score=row["freshness_score"] or 100.0,
            )
        )

    return previews


# =============================================================================
# POLLS
# =============================================================================


def load_polls(conn: sqlite3.Connection, creator_id: str) -> list[Poll]:
    """
    Load available polls for creator.

    Polls are interactive engagement tools with 2-4 options.
    Categories: preference, tease, feedback, interactive

    Args:
        conn: Database connection
        creator_id: Creator UUID

    Returns:
        List of Poll objects sorted by performance score
    """
    Poll = _get_poll_class()

    query = """
        SELECT
            p.poll_id,
            p.question_text,
            p.option_1,
            p.option_2,
            p.option_3,
            p.option_4,
            p.duration_hours,
            p.poll_category,
            p.tone,
            p.performance_score
        FROM poll_bank p
        WHERE p.is_active = 1
          AND (p.creator_id = ? OR p.is_universal = 1)
        ORDER BY p.performance_score DESC
        LIMIT 20
    """
    cursor = conn.execute(query, (creator_id,))

    polls = []
    for row in cursor.fetchall():
        # Build options list from non-null option columns
        options = [row["option_1"], row["option_2"]]
        if row["option_3"]:
            options.append(row["option_3"])
        if row["option_4"]:
            options.append(row["option_4"])

        polls.append(
            Poll(
                poll_id=row["poll_id"],
                question_text=row["question_text"],
                options=options,
                duration_hours=row["duration_hours"] or 24,
                poll_category=row["poll_category"] or "interactive",
                tone=row["tone"],
            )
        )

    return polls


# =============================================================================
# GAME WHEEL
# =============================================================================


def load_game_wheel_config(conn: sqlite3.Connection, creator_id: str) -> GameWheelConfig | None:
    """
    Load active game wheel configuration for creator.

    Returns the first active wheel configuration, or None if no wheel is set up.

    Args:
        conn: Database connection
        creator_id: Creator UUID

    Returns:
        GameWheelConfig object or None if not configured
    """
    import json

    GameWheelConfig = _get_game_wheel_config_class()

    query = """
        SELECT
            wheel_id,
            wheel_name,
            spin_trigger,
            min_trigger_amount,
            segment_count,
            segments_json,
            display_text,
            cooldown_hours
        FROM game_wheel_configs
        WHERE creator_id = ? AND is_active = 1
        LIMIT 1
    """
    cursor = conn.execute(query, (creator_id,))
    row = cursor.fetchone()

    if not row:
        return None

    # Parse segments JSON
    try:
        segments = json.loads(row["segments_json"]) if row["segments_json"] else []
    except json.JSONDecodeError:
        segments = []

    return GameWheelConfig(
        wheel_id=row["wheel_id"],
        wheel_name=row["wheel_name"],
        spin_trigger=row["spin_trigger"] or "tip",
        min_trigger_amount=row["min_trigger_amount"] or 5.00,
        segments=segments,
        display_text=row["display_text"],
        cooldown_hours=row["cooldown_hours"] or 24,
    )


# =============================================================================
# PERSONA SCORING FOR NEW CONTENT TYPES
# =============================================================================


def apply_preview_persona_scores(
    previews: list[FreePreview], profile: CreatorProfile
) -> list[FreePreview]:
    """
    Apply persona boost scores to free previews.

    Uses tone matching similar to caption persona scoring.

    Args:
        previews: List of FreePreview objects
        profile: CreatorProfile with persona attributes

    Returns:
        List of previews with persona_boost set
    """
    for preview in previews:
        boost = 1.0

        # Tone matching
        if preview.tone and profile.primary_tone:
            if preview.tone.lower() == profile.primary_tone.lower():
                boost *= 1.15

        preview.persona_boost = boost

    return previews


def apply_poll_persona_scores(polls: list[Poll], profile: CreatorProfile) -> list[Poll]:
    """
    Apply persona boost scores to polls.

    Uses tone matching to prefer polls that match creator voice.

    Args:
        polls: List of Poll objects
        profile: CreatorProfile with persona attributes

    Returns:
        List of polls with persona_boost set
    """
    for poll in polls:
        boost = 1.0

        # Tone matching
        if poll.tone and profile.primary_tone:
            if poll.tone.lower() == profile.primary_tone.lower():
                boost *= 1.15

        poll.persona_boost = boost

    return polls


# =============================================================================
# TIER 1-2 REVENUE CONTENT LOADERS
# =============================================================================


def load_tip_incentive_posts(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load tip incentive post templates.

    Includes both creator-specific and universal templates (is_universal=1).
    These posts encourage tipping with rewards/incentives (first_to_tip campaigns).

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of tip incentive template dicts with persona scoring
    """
    # Check if tip_incentive_templates table exists
    try:
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='tip_incentive_templates'
            """
        )
        table_exists = cursor.fetchone() is not None
    except sqlite3.Error:
        table_exists = False

    if table_exists:
        query = """
            SELECT
                template_id AS content_id,
                template_text AS content_text,
                'first_to_tip' AS content_type,
                tone,
                emoji_style,
                slang_level,
                performance_score,
                freshness_score,
                is_universal,
                tip_goal,
                reward_type
            FROM tip_incentive_templates
            WHERE is_active = 1
              AND (creator_id = ? OR is_universal = 1)
            ORDER BY performance_score DESC
            LIMIT 20
        """
    else:
        # Fallback to caption_bank
        query = """
            SELECT
                cb.caption_id AS content_id,
                cb.caption_text AS content_text,
                'first_to_tip' AS content_type,
                cb.tone,
                cb.emoji_style,
                cb.slang_level,
                cb.performance_score,
                cb.freshness_score,
                cb.is_universal,
                NULL AS tip_goal,
                NULL AS reward_type
            FROM caption_bank cb
            WHERE cb.is_active = 1
              AND (cb.caption_type LIKE '%tip%' OR cb.caption_type LIKE '%incentive%')
              AND (cb.creator_id = ? OR cb.is_universal = 1)
            ORDER BY cb.performance_score DESC
            LIMIT 20
        """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("first_to_tip")]

    if not rows:
        return [_create_placeholder_content("first_to_tip")]

    items = []
    for row in rows:
        item = {
            "content_id": row["content_id"],
            "content_text": row["content_text"],
            "content_type": "first_to_tip",
            "has_caption": bool(row["content_text"]),
            "theme_guidance": get_theme_guidance("first_to_tip"),
            "freshness_score": row["freshness_score"] or 100.0,
            "performance_score": row["performance_score"] or 50.0,
            "tone": row["tone"],
            "emoji_style": row["emoji_style"],
            "slang_level": row["slang_level"],
            "is_universal": bool(row["is_universal"]),
        }
        # Add optional tip incentive fields if available
        if "tip_goal" in row.keys() and row["tip_goal"]:
            item["tip_goal"] = row["tip_goal"]
        if "reward_type" in row.keys() and row["reward_type"]:
            item["reward_type"] = row["reward_type"]
        items.append(item)

    return apply_generic_persona_scores(items, persona)


def load_bundle_posts(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
    min_freshness: float = 30.0,
) -> list[dict]:
    """
    Load bundle post captions from caption_bank.

    Queries caption_bank for schedulable_type = 'bundle' or caption_type = 'bundle'.
    Filters by freshness >= 30 (default) for quality content.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring
        min_freshness: Minimum freshness score (default: 30.0)

    Returns:
        List of bundle caption dicts with persona scoring
    """
    query = """
        SELECT
            cb.caption_id AS content_id,
            cb.caption_text AS content_text,
            'bundle' AS content_type,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND (cb.caption_type = 'bundle' OR cb.caption_type LIKE '%bundle%')
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 30
    """
    try:
        cursor = conn.execute(query, (creator_id, min_freshness))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("bundle")]

    if not rows:
        return [_create_placeholder_content("bundle")]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "bundle",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("bundle"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
            }
        )

    return apply_generic_persona_scores(items, persona)


def load_flash_bundles(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
    min_freshness: float = 30.0,
) -> list[dict]:
    """
    Load flash bundle captions with scarcity messaging flag.

    Flash bundles are time-limited offers requiring urgency. The is_flash
    flag indicates scarcity messaging should be applied.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring
        min_freshness: Minimum freshness score (default: 30.0)

    Returns:
        List of flash bundle dicts with is_flash=True flag
    """
    query = """
        SELECT
            cb.caption_id AS content_id,
            cb.caption_text AS content_text,
            'flash_bundle' AS content_type,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND (cb.caption_type = 'flash_bundle' OR cb.caption_type LIKE '%flash%')
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 20
    """
    try:
        cursor = conn.execute(query, (creator_id, min_freshness))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("flash_bundle", {"is_flash": True})]

    if not rows:
        return [_create_placeholder_content("flash_bundle", {"is_flash": True})]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "flash_bundle",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("flash_bundle"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
                "is_flash": True,  # Flag for scarcity messaging
            }
        )

    return apply_generic_persona_scores(items, persona)


def load_snapchat_bundles(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
    min_freshness: float = 30.0,
) -> list[dict]:
    """
    Load Snapchat bundle captions for premium access offers.

    Snapchat bundles offer premium Snapchat access as a cross-platform promotion.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring
        min_freshness: Minimum freshness score (default: 30.0)

    Returns:
        List of Snapchat bundle dicts with persona scoring
    """
    query = """
        SELECT
            cb.caption_id AS content_id,
            cb.caption_text AS content_text,
            'snapchat_bundle' AS content_type,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND (cb.caption_type = 'snapchat_bundle' OR cb.caption_type LIKE '%snapchat%')
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= ?
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 20
    """
    try:
        cursor = conn.execute(query, (creator_id, min_freshness))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("snapchat_bundle")]

    if not rows:
        return [_create_placeholder_content("snapchat_bundle")]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "snapchat_bundle",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("snapchat_bundle"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
            }
        )

    return apply_generic_persona_scores(items, persona)


def load_link_drops(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load link drop templates for cross-platform promotion.

    Includes both universal and creator-specific link drop templates.
    Falls back to caption_bank if link_drop_templates table doesn't exist.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of link drop template dicts with persona scoring
    """
    # Check if link_drop_templates table exists
    try:
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='link_drop_templates'
            """
        )
        table_exists = cursor.fetchone() is not None
    except sqlite3.Error:
        table_exists = False

    if table_exists:
        query = """
            SELECT
                template_id AS content_id,
                template_text AS content_text,
                'link_drop' AS content_type,
                tone,
                emoji_style,
                slang_level,
                performance_score,
                freshness_score,
                is_universal,
                link_url,
                platform
            FROM link_drop_templates
            WHERE is_active = 1
              AND (creator_id = ? OR is_universal = 1)
            ORDER BY performance_score DESC
            LIMIT 30
        """
    else:
        # Fallback to caption_bank
        query = """
            SELECT
                cb.caption_id AS content_id,
                cb.caption_text AS content_text,
                'link_drop' AS content_type,
                cb.tone,
                cb.emoji_style,
                cb.slang_level,
                cb.performance_score,
                cb.freshness_score,
                cb.is_universal,
                NULL AS link_url,
                NULL AS platform
            FROM caption_bank cb
            WHERE cb.is_active = 1
              AND (cb.caption_type = 'link_drop' OR cb.caption_type LIKE '%link%')
              AND (cb.creator_id = ? OR cb.is_universal = 1)
            ORDER BY cb.performance_score DESC
            LIMIT 30
        """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("link_drop")]

    if not rows:
        return [_create_placeholder_content("link_drop")]

    items = []
    for row in rows:
        item = {
            "content_id": row["content_id"],
            "content_text": row["content_text"],
            "content_type": "link_drop",
            "has_caption": bool(row["content_text"]),
            "theme_guidance": get_theme_guidance("link_drop"),
            "freshness_score": row["freshness_score"] or 100.0,
            "performance_score": row["performance_score"] or 50.0,
            "tone": row["tone"],
            "emoji_style": row["emoji_style"],
            "slang_level": row["slang_level"],
            "is_universal": bool(row["is_universal"]),
        }
        # Add optional link fields if available
        if "link_url" in row.keys() and row["link_url"]:
            item["link_url"] = row["link_url"]
        if "platform" in row.keys() and row["platform"]:
            item["platform"] = row["platform"]
        items.append(item)

    return apply_generic_persona_scores(items, persona)


def load_live_promos(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load live stream promotion content.

    Queries caption_bank for live promo captions. If none exist,
    returns a placeholder with theme guidance.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of live promo dicts with persona scoring
    """
    query = """
        SELECT
            cb.caption_id AS content_id,
            cb.caption_text AS content_text,
            'live_promo' AS content_type,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND (cb.caption_type = 'live_promo' OR cb.caption_type LIKE '%live%')
          AND (cb.creator_id = ? OR cb.is_universal = 1)
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 20
    """
    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("live_promo")]

    if not rows:
        return [_create_placeholder_content("live_promo")]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "live_promo",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("live_promo"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
            }
        )

    return apply_generic_persona_scores(items, persona)


# =============================================================================
# BUMP CONTENT LOADERS
# =============================================================================


def load_normal_bumps(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load normal bump captions for wall posts.

    Queries caption_bank for bump_short captions marked as wall-eligible.
    These are short engagement bumps for the feed.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of normal bump dicts with persona scoring
    """
    query = """
        SELECT
            cb.caption_id AS content_id,
            cb.caption_text AS content_text,
            'normal_post_bump' AS content_type,
            cb.tone,
            cb.emoji_style,
            cb.slang_level,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND cb.caption_type = 'bump_short'
          AND cb.is_wall_eligible = 1
          AND (cb.creator_id = ? OR cb.is_universal = 1)
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 50
    """
    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.Error:
        return [_create_placeholder_content("normal_post_bump")]

    if not rows:
        return [_create_placeholder_content("normal_post_bump")]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "normal_post_bump",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("normal_post_bump"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
            }
        )

    return apply_generic_persona_scores(items, persona)


def load_flyer_gif_bumps(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load flyer/GIF bump variants for visual engagement.

    Queries bump_variants table for flyer_gif type bumps.
    Falls back to placeholder if table doesn't exist.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of flyer/GIF bump dicts with persona scoring
    """
    # Check if bump_variants table exists
    try:
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bump_variants'
            """
        )
        table_exists = cursor.fetchone() is not None
    except sqlite3.Error:
        table_exists = False

    if table_exists:
        query = """
            SELECT
                variant_id AS content_id,
                variant_text AS content_text,
                'flyer_gif_bump' AS content_type,
                tone,
                emoji_style,
                slang_level,
                performance_score,
                freshness_score,
                is_universal,
                media_url
            FROM bump_variants
            WHERE is_active = 1
              AND bump_type = 'flyer_gif'
              AND (creator_id = ? OR is_universal = 1)
            ORDER BY performance_score DESC
            LIMIT 30
        """
        try:
            cursor = conn.execute(query, (creator_id,))
            rows = cursor.fetchall()
        except sqlite3.Error:
            rows = []
    else:
        rows = []

    if not rows:
        return [_create_placeholder_content("flyer_gif_bump")]

    items = []
    for row in rows:
        item = {
            "content_id": row["content_id"],
            "content_text": row["content_text"],
            "content_type": "flyer_gif_bump",
            "has_caption": bool(row["content_text"]),
            "theme_guidance": get_theme_guidance("flyer_gif_bump"),
            "freshness_score": row["freshness_score"] or 100.0,
            "performance_score": row["performance_score"] or 50.0,
            "tone": row["tone"],
            "emoji_style": row["emoji_style"],
            "slang_level": row["slang_level"],
            "is_universal": bool(row["is_universal"]),
        }
        if "media_url" in row.keys() and row["media_url"]:
            item["media_url"] = row["media_url"]
        items.append(item)

    return apply_generic_persona_scores(items, persona)


def load_descriptive_bumps(
    conn: sqlite3.Connection,
    creator_id: str,
    persona: dict,
) -> list[dict]:
    """
    Load descriptive bump variants for detailed content previews.

    Queries bump_variants table for descriptive type bumps.
    Falls back to placeholder if table doesn't exist.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dict for scoring

    Returns:
        List of descriptive bump dicts with persona scoring
    """
    # Check if bump_variants table exists
    try:
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bump_variants'
            """
        )
        table_exists = cursor.fetchone() is not None
    except sqlite3.Error:
        table_exists = False

    if table_exists:
        query = """
            SELECT
                variant_id AS content_id,
                variant_text AS content_text,
                'descriptive_bump' AS content_type,
                tone,
                emoji_style,
                slang_level,
                performance_score,
                freshness_score,
                is_universal
            FROM bump_variants
            WHERE is_active = 1
              AND bump_type = 'descriptive'
              AND (creator_id = ? OR is_universal = 1)
            ORDER BY performance_score DESC
            LIMIT 30
        """
        try:
            cursor = conn.execute(query, (creator_id,))
            rows = cursor.fetchall()
        except sqlite3.Error:
            rows = []
    else:
        rows = []

    if not rows:
        return [_create_placeholder_content("descriptive_bump")]

    items = []
    for row in rows:
        items.append(
            {
                "content_id": row["content_id"],
                "content_text": row["content_text"],
                "content_type": "descriptive_bump",
                "has_caption": bool(row["content_text"]),
                "theme_guidance": get_theme_guidance("descriptive_bump"),
                "freshness_score": row["freshness_score"] or 100.0,
                "performance_score": row["performance_score"] or 50.0,
                "tone": row["tone"],
                "emoji_style": row["emoji_style"],
                "slang_level": row["slang_level"],
                "is_universal": bool(row["is_universal"]),
            }
        )

    return apply_generic_persona_scores(items, persona)


# =============================================================================
# TIER 3 - ENGAGEMENT LOADERS
# =============================================================================


def load_dm_farm_content(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Load DM farm content templates for engagement drives.

    DM farm content encourages fans to initiate conversations, driving
    engagement metrics and opening opportunities for custom content sales.

    Theme: "DM me for surprise, encourage fan interaction"

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for DM farm slots
    """
    query = """
        SELECT
            et.template_id,
            et.template_text,
            et.engagement_type,
            et.tone,
            et.performance_score,
            et.freshness_score,
            et.is_universal
        FROM engagement_templates et
        WHERE et.is_active = 1
          AND et.engagement_type = 'dm_farm'
          AND (et.creator_id = ? OR et.is_universal = 1)
        ORDER BY et.performance_score DESC, et.freshness_score DESC
        LIMIT 50
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # Table doesn't exist yet - return empty list
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="dm_farm",
            has_caption=True,
            theme_guidance="DM me for surprise, encourage fan interaction",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=False,
            channel="direct",
            tone=row["tone"],
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


def load_like_farm_content(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Load like farm content templates for engagement campaigns.

    Like farm posts encourage fans to like all posts for rewards,
    boosting engagement metrics and algorithm visibility.

    Theme: "Like all posts for reward, boost engagement metrics"

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for like farm slots
    """
    query = """
        SELECT
            et.template_id,
            et.template_text,
            et.engagement_type,
            et.tone,
            et.performance_score,
            et.freshness_score,
            et.is_universal
        FROM engagement_templates et
        WHERE et.is_active = 1
          AND et.engagement_type = 'like_farm'
          AND (et.creator_id = ? OR et.is_universal = 1)
        ORDER BY et.performance_score DESC, et.freshness_score DESC
        LIMIT 50
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="like_farm",
            has_caption=True,
            theme_guidance="Like all posts for reward, boost engagement metrics",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=True,  # Like farms usually have eye-catching visuals
            channel="feed",
            tone=row["tone"],
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


def load_text_only_bumps(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Load text-only bump variants for quick engagement.

    Text-only bumps are short, flirty messages without media attachments.
    They feel personal and spontaneous, like quick check-ins.

    Theme: Short flirty text like "wyd right now daddy"

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for text-only bump slots
    """
    query = """
        SELECT
            bv.variant_id,
            bv.variant_text,
            bv.bump_type,
            bv.tone,
            bv.performance_score,
            bv.freshness_score,
            bv.is_universal
        FROM bump_variants bv
        WHERE bv.is_active = 1
          AND bv.bump_type = 'text_only'
          AND (bv.creator_id = ? OR bv.is_universal = 1)
        ORDER BY bv.performance_score DESC, bv.freshness_score DESC
        LIMIT 50
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["variant_id"],
            content_text=row["variant_text"],
            content_type="text_only_bump",
            has_caption=True,
            theme_guidance="Personal message tone, casual check-in or tease",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=False,  # No media required
            channel="mass_message",
            tone=row["tone"],
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


def load_wall_link_drops(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Load wall link drop templates for cross-promotion.

    Wall link drops promote wall post campaigns and drive traffic
    to specific content or external platforms.

    Theme: "For promoting wall post campaigns"

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for wall link drop slots
    """
    query = """
        SELECT
            ldt.template_id,
            ldt.template_text,
            ldt.link_type,
            ldt.tone,
            ldt.performance_score,
            ldt.freshness_score,
            ldt.is_universal
        FROM link_drop_templates ldt
        WHERE ldt.is_active = 1
          AND ldt.link_type = 'wall_post'
          AND (ldt.creator_id = ? OR ldt.is_universal = 1)
        ORDER BY ldt.performance_score DESC, ldt.freshness_score DESC
        LIMIT 50
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="wall_link_drop",
            has_caption=True,
            theme_guidance="Quick link share on wall, casual promotion",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=False,
            channel="feed",
            tone=row["tone"],
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


# =============================================================================
# TIER 4 - RETENTION LOADERS (PAID PAGES ONLY)
# =============================================================================


@paid_page_only
def load_renew_on_posts(
    conn: sqlite3.Connection, creator_id: str, page_type: str, persona: dict
) -> list[dict]:
    """
    Load renewal reminder post templates for subscriber retention.

    Renew-on posts remind subscribers of the value they receive
    and encourage subscription renewal before expiration.

    Includes renew link: https://onlyfans.com/{page_name}?enable_renew=1

    PAID PAGES ONLY - Returns empty list for free pages.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        page_type: Page type ("paid" or "free")
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for renewal post slots
    """
    # First get the creator's page_name for the renew link
    page_name_query = """
        SELECT page_name FROM creators WHERE creator_id = ?
    """
    try:
        cursor = conn.execute(page_name_query, (creator_id,))
        row = cursor.fetchone()
        page_name = row["page_name"] if row else "unknown"
    except sqlite3.OperationalError:
        page_name = "unknown"

    renew_link = f"https://onlyfans.com/{page_name}?enable_renew=1"

    query = """
        SELECT
            rt.template_id,
            rt.template_text,
            rt.retention_type,
            rt.tone,
            rt.performance_score,
            rt.freshness_score,
            rt.is_universal
        FROM retention_templates rt
        WHERE rt.is_active = 1
          AND rt.retention_type = 'renew_on_post'
          AND (rt.creator_id = ? OR rt.is_universal = 1)
        ORDER BY rt.performance_score DESC, rt.freshness_score DESC
        LIMIT 30
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="renew_on_post",
            has_caption=True,
            theme_guidance="Subscription value reminder, upcoming content tease",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=True,
            channel="feed",
            tone=row["tone"],
            extra_data={"renew_link": renew_link, "page_name": page_name},
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


@paid_page_only
def load_renew_on_mm(
    conn: sqlite3.Connection, creator_id: str, page_type: str, persona: dict
) -> list[dict]:
    """
    Load renewal reminder mass message templates.

    Mass message version of renewal reminders with incentive offers
    to encourage subscription renewal before expiration.

    PAID PAGES ONLY - Returns empty list for free pages.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        page_type: Page type ("paid" or "free")
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for renewal mass message slots
    """
    # Get the creator's page_name for the renew link
    page_name_query = """
        SELECT page_name FROM creators WHERE creator_id = ?
    """
    try:
        cursor = conn.execute(page_name_query, (creator_id,))
        row = cursor.fetchone()
        page_name = row["page_name"] if row else "unknown"
    except sqlite3.OperationalError:
        page_name = "unknown"

    renew_link = f"https://onlyfans.com/{page_name}?enable_renew=1"

    query = """
        SELECT
            rt.template_id,
            rt.template_text,
            rt.retention_type,
            rt.tone,
            rt.performance_score,
            rt.freshness_score,
            rt.incentive_offer,
            rt.is_universal
        FROM retention_templates rt
        WHERE rt.is_active = 1
          AND rt.retention_type = 'renew_on_mm'
          AND (rt.creator_id = ? OR rt.is_universal = 1)
        ORDER BY rt.performance_score DESC, rt.freshness_score DESC
        LIMIT 30
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="renew_on_mm",
            has_caption=True,
            theme_guidance="Subscription expiring soon, exclusive content preview to retain",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=True,
            channel="mass_message",
            tone=row["tone"],
            extra_data={
                "renew_link": renew_link,
                "page_name": page_name,
                "incentive_offer": row.get("incentive_offer"),
            },
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


@paid_page_only
def load_expired_subscriber_content(
    conn: sqlite3.Connection, creator_id: str, page_type: str, persona: dict
) -> list[dict]:
    """
    Load expired subscriber win-back message templates.

    Win-back messaging targets expired subscribers with special offers
    and content previews to encourage re-subscription.

    Must match current subscription incentive.

    PAID PAGES ONLY - Returns empty list for free pages.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        page_type: Page type ("paid" or "free")
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for expired subscriber outreach
    """
    # Get current subscription incentive for matching
    incentive_query = """
        SELECT current_sub_incentive FROM creators WHERE creator_id = ?
    """
    try:
        cursor = conn.execute(incentive_query, (creator_id,))
        row = cursor.fetchone()
        current_incentive = row["current_sub_incentive"] if row else None
    except sqlite3.OperationalError:
        current_incentive = None

    query = """
        SELECT
            rt.template_id,
            rt.template_text,
            rt.retention_type,
            rt.tone,
            rt.performance_score,
            rt.freshness_score,
            rt.incentive_offer,
            rt.is_universal
        FROM retention_templates rt
        WHERE rt.is_active = 1
          AND rt.retention_type = 'expired_subscriber'
          AND (rt.creator_id = ? OR rt.is_universal = 1)
        ORDER BY rt.performance_score DESC, rt.freshness_score DESC
        LIMIT 30
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["template_id"],
            content_text=row["template_text"],
            content_type="expired_subscriber",
            has_caption=True,
            theme_guidance="Miss you message, highlight what they are missing, special offer to return",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=True,
            channel="direct",
            tone=row["tone"],
            extra_data={
                "incentive_offer": row.get("incentive_offer"),
                "current_incentive": current_incentive,
            },
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


@paid_page_only
def load_vip_posts(
    conn: sqlite3.Connection, creator_id: str, page_type: str, persona: dict
) -> list[dict]:
    """
    Load VIP tier exclusive post templates.

    VIP posts promote exclusive $200+ VIP tier content and benefits,
    driving upgrades to premium subscription tiers.

    PAID PAGES ONLY - Returns empty list for free pages.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        page_type: Page type ("paid" or "free")
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for VIP post slots
    """
    query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.caption_type,
            cb.tone,
            cb.performance_score,
            cb.freshness_score,
            cb.is_universal
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND cb.schedulable_type = 'vip_post'
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= 30.0
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 30
    """

    try:
        cursor = conn.execute(query, (creator_id,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []

    contents = []
    for row in rows:
        content = _create_engagement_content(
            content_id=row["caption_id"],
            content_text=row["caption_text"],
            content_type="vip_post",
            has_caption=True,
            theme_guidance="Exclusive tier promotion, emphasize $200+ VIP value and premium benefits",
            freshness_score=row["freshness_score"] or 100.0,
            performance_score=row["performance_score"] or 50.0,
            requires_flyer=True,
            channel="feed",
            tone=row["tone"],
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


def load_game_posts(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Load game/gamification post templates.

    Game posts include wheel spins, contests, and other gamification
    elements that drive engagement through interactive content.

    Theme: "Spin the wheel, chance to win, gamification"

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries for game post slots
    """
    import json

    # First try to get game wheel configs
    wheel_query = """
        SELECT
            gwc.wheel_id,
            gwc.wheel_name,
            gwc.display_text,
            gwc.segments_json,
            gwc.spin_trigger,
            gwc.min_trigger_amount
        FROM game_wheel_configs gwc
        WHERE gwc.is_active = 1
          AND gwc.creator_id = ?
        ORDER BY gwc.wheel_id DESC
        LIMIT 10
    """

    contents = []

    try:
        cursor = conn.execute(wheel_query, (creator_id,))
        rows = cursor.fetchall()

        for row in rows:
            try:
                segments = json.loads(row["segments_json"]) if row["segments_json"] else []
            except json.JSONDecodeError:
                segments = []

            content = _create_engagement_content(
                content_id=row["wheel_id"],
                content_text=row["display_text"],
                content_type="game_post",
                has_caption=bool(row["display_text"]),
                theme_guidance="Spin the wheel, chance to win prizes, gamification and fun",
                freshness_score=100.0,  # Wheels are always fresh
                performance_score=70.0,  # Games typically perform well
                requires_flyer=True,
                channel="feed",
                extra_data={
                    "wheel_name": row["wheel_name"],
                    "segments": segments,
                    "spin_trigger": row["spin_trigger"],
                    "min_trigger_amount": row["min_trigger_amount"],
                },
            )
            contents.append(_apply_persona_boost(content, persona))

    except sqlite3.OperationalError:
        pass

    # Also try caption_bank for game posts
    caption_query = """
        SELECT
            cb.caption_id,
            cb.caption_text,
            cb.tone,
            cb.performance_score,
            cb.freshness_score
        FROM caption_bank cb
        WHERE cb.is_active = 1
          AND cb.schedulable_type = 'game_post'
          AND (cb.creator_id = ? OR cb.is_universal = 1)
          AND cb.freshness_score >= 30.0
        ORDER BY cb.performance_score DESC, cb.freshness_score DESC
        LIMIT 20
    """

    try:
        cursor = conn.execute(caption_query, (creator_id,))
        rows = cursor.fetchall()

        for row in rows:
            content = _create_engagement_content(
                content_id=row["caption_id"],
                content_text=row["caption_text"],
                content_type="game_post",
                has_caption=True,
                theme_guidance="Spin the wheel, chance to win prizes, gamification and fun",
                freshness_score=row["freshness_score"] or 100.0,
                performance_score=row["performance_score"] or 50.0,
                requires_flyer=True,
                channel="feed",
                tone=row["tone"],
            )
            contents.append(_apply_persona_boost(content, persona))

    except sqlite3.OperationalError:
        pass

    return contents


# =============================================================================
# UNIFIED CONTENT LOADER
# =============================================================================


def create_placeholder(content_type: str) -> dict:
    """
    Create placeholder content dictionary for types without captions.

    When no captions exist for a content type, this creates a placeholder
    with theme guidance that can be used for manual content creation.

    Args:
        content_type: The content type ID (e.g., "dm_farm", "vip_post")

    Returns:
        Placeholder content dictionary with theme guidance
    """
    from content_type_registry import REGISTRY

    try:
        type_info = REGISTRY.get(content_type)
        theme_guidance = type_info.theme_guidance
        requires_flyer = type_info.requires_flyer
        channel = type_info.channel
    except KeyError:
        # Unknown content type - use defaults
        theme_guidance = f"Content for {content_type} slot"
        requires_flyer = True
        channel = "mass_message"

    return {
        "content_id": None,
        "content_text": None,
        "content_type": content_type,
        "has_caption": False,
        "theme_guidance": theme_guidance,
        "freshness_score": 100.0,
        "performance_score": 50.0,
        "persona_boost": 1.0,
        "requires_flyer": requires_flyer,
        "channel": channel,
    }


def load_content_by_type(
    conn: sqlite3.Connection,
    creator_id: str,
    content_type: str,
    page_type: str,
    persona: dict,
) -> list[dict]:
    """
    Unified loader that routes to appropriate loader based on content type.

    This function provides a single entry point for loading any content type,
    automatically handling page type validation and routing to the correct
    specialized loader function.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        content_type: Content type ID (e.g., "ppv", "dm_farm", "vip_post")
        page_type: Page type ("paid" or "free")
        persona: Creator persona dictionary with tone preferences

    Returns:
        List of content dictionaries, or [placeholder] if no content exists

    Example:
        >>> content = load_content_by_type(conn, creator_id, "dm_farm", "paid", persona)
        >>> for item in content:
        ...     print(item["content_text"])
    """
    from content_type_registry import REGISTRY

    # Validate page type first
    try:
        if not REGISTRY.validate_for_page(content_type, page_type):
            return []
    except KeyError:
        # Unknown content type - proceed with loading attempt
        pass

    # Map content types to their loader functions
    # Note: Functions with page_type parameter are marked with a flag
    loaders: dict[str, tuple[Callable, bool]] = {
        # Tier 1 - Direct Revenue
        "bundle": (load_bundle_posts, False),
        "flash_bundle": (load_flash_bundles, False),
        "snapchat_bundle": (load_snapchat_bundles, False),
        # Tier 2 - Feed/Wall
        "wall_post": (load_wall_post_captions_as_dicts, False),
        "vip_post": (load_vip_posts, True),  # page_type required
        "first_to_tip": (load_tip_incentive_posts, False),
        "link_drop": (load_link_drops, False),
        "live_promo": (load_live_promos, False),
        "game_post": (load_game_posts, False),
        "wall_link_drop": (load_wall_link_drops, False),
        "normal_post_bump": (load_normal_bumps, False),
        "flyer_gif_bump": (load_flyer_gif_bumps, False),
        "descriptive_bump": (load_descriptive_bumps, False),
        # Tier 3 - Engagement
        "dm_farm": (load_dm_farm_content, False),
        "like_farm": (load_like_farm_content, False),
        "text_only_bump": (load_text_only_bumps, False),
        # Tier 4 - Retention (all require page_type)
        "renew_on_post": (load_renew_on_posts, True),
        "renew_on_mm": (load_renew_on_mm, True),
        "expired_subscriber": (load_expired_subscriber_content, True),
    }

    loader_info = loaders.get(content_type)
    if loader_info:
        loader_func, needs_page_type = loader_info
        try:
            if needs_page_type:
                result = loader_func(conn, creator_id, page_type, persona)
            else:
                result = loader_func(conn, creator_id, persona)

            if result:
                return result
        except Exception:
            # Log error but continue to placeholder
            pass

    # Return placeholder if no content found
    return [create_placeholder(content_type)]


def load_wall_post_captions_as_dicts(
    conn: sqlite3.Connection, creator_id: str, persona: dict
) -> list[dict]:
    """
    Wrapper to load wall post captions as dictionaries.

    Converts Caption dataclass instances to dictionaries for unified loading.

    Args:
        conn: Database connection
        creator_id: Creator UUID
        persona: Creator persona dictionary

    Returns:
        List of content dictionaries
    """
    captions = load_wall_post_captions(conn, creator_id)

    contents = []
    for caption in captions:
        content = _create_engagement_content(
            content_id=caption.caption_id,
            content_text=caption.caption_text,
            content_type="wall_post",
            has_caption=True,
            theme_guidance="Casual engagement post, encourage likes and comments",
            freshness_score=caption.freshness_score,
            performance_score=caption.performance_score,
            requires_flyer=True,
            channel="feed",
            tone=caption.tone,
        )
        contents.append(_apply_persona_boost(content, persona))

    return contents


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Original loaders
    "load_wall_post_captions",
    "load_free_previews",
    "load_polls",
    "load_game_wheel_config",
    "apply_preview_persona_scores",
    "apply_poll_persona_scores",
    # Tier 1-2 Revenue content loaders
    "load_tip_incentive_posts",
    "load_bundle_posts",
    "load_flash_bundles",
    "load_snapchat_bundles",
    "load_link_drops",
    "load_live_promos",
    # Bump loaders
    "load_normal_bumps",
    "load_flyer_gif_bumps",
    "load_descriptive_bumps",
    # Tier 3 - Engagement loaders
    "load_dm_farm_content",
    "load_like_farm_content",
    "load_text_only_bumps",
    "load_wall_link_drops",
    # Tier 4 - Retention loaders (paid only)
    "load_renew_on_posts",
    "load_renew_on_mm",
    "load_expired_subscriber_content",
    "load_vip_posts",
    "load_game_posts",
    # Unified loader
    "load_content_by_type",
    "create_placeholder",
    # Helper functions
    "get_theme_guidance",
    "apply_generic_persona_scores",
    # Decorators and helpers
    "paid_page_only",
]
