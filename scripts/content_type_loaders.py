#!/usr/bin/env python3
"""
Content Type Loaders - Load various content types for scheduling.

This module provides loading functions for:
- Wall/Feed posts (captions marked as wall-eligible)
- Free previews (teaser content)
- Polls (interactive engagement)
- Game wheel configurations (gamification)

All functions accept a SQLite connection and creator_id,
returning typed data class instances from generate_schedule.

Note: Uses lazy imports to avoid circular import issues with generate_schedule.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

# Type hints only - these won't cause circular imports
if TYPE_CHECKING:
    from generate_schedule import (
        Caption,
        FreePreview,
        Poll,
        GameWheelConfig,
        CreatorProfile,
    )


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
# WALL POST CAPTIONS
# =============================================================================

def load_wall_post_captions(
    conn: sqlite3.Connection,
    creator_id: str,
    min_freshness: float = 30.0
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
        captions.append(Caption(
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
            is_universal=bool(row["is_universal"])
        ))

    return captions


# =============================================================================
# FREE PREVIEWS
# =============================================================================

def load_free_previews(
    conn: sqlite3.Connection,
    creator_id: str,
    min_freshness: float = 30.0
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
        previews.append(FreePreview(
            preview_id=row["preview_id"],
            preview_text=row["preview_text"],
            preview_type=row["preview_type"],
            content_type_id=row["content_type_id"],
            linked_ppv_type=row["linked_ppv_type"],
            tone=row["tone"],
            performance_score=row["performance_score"] or 50.0,
            freshness_score=row["freshness_score"] or 100.0
        ))

    return previews


# =============================================================================
# POLLS
# =============================================================================

def load_polls(
    conn: sqlite3.Connection,
    creator_id: str
) -> list[Poll]:
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

        polls.append(Poll(
            poll_id=row["poll_id"],
            question_text=row["question_text"],
            options=options,
            duration_hours=row["duration_hours"] or 24,
            poll_category=row["poll_category"] or "interactive",
            tone=row["tone"]
        ))

    return polls


# =============================================================================
# GAME WHEEL
# =============================================================================

def load_game_wheel_config(
    conn: sqlite3.Connection,
    creator_id: str
) -> GameWheelConfig | None:
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
        cooldown_hours=row["cooldown_hours"] or 24
    )


# =============================================================================
# PERSONA SCORING FOR NEW CONTENT TYPES
# =============================================================================

def apply_preview_persona_scores(
    previews: list[FreePreview],
    profile: CreatorProfile
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


def apply_poll_persona_scores(
    polls: list[Poll],
    profile: CreatorProfile
) -> list[Poll]:
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
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "load_wall_post_captions",
    "load_free_previews",
    "load_polls",
    "load_game_wheel_config",
    "apply_preview_persona_scores",
    "apply_poll_persona_scores",
]
