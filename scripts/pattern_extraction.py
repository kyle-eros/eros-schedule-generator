#!/usr/bin/env python3
"""
Pattern Extraction - Build pattern profiles from historical performance data.

This module implements a two-tier pattern extraction system that analyzes
historical mass_message performance to guide caption selection. Pattern profiles
predict the likely performance of fresh/unused captions based on their attributes.

Two-Tier Pattern Extraction:
    Tier 1 (Combined): Patterns combining content_type + tone + hook_type
        - Requires 3+ samples per pattern for statistical significance
        - Most specific prediction of caption performance
        - Pattern key format: "content_type|tone|hook_type"

    Tier 2 (Individual): Fallback patterns for sparse data
        - Content type patterns (e.g., "sextape" -> PatternStats)
        - Tone patterns (e.g., "playful" -> PatternStats)
        - Hook type patterns (e.g., "question" -> PatternStats)

Global Fallback:
    For new creators with insufficient data (<20 sends), a global portfolio-wide
    pattern profile is used with a 0.7x discount on scores.

Confidence Scoring:
    - <20 samples: 0.5 confidence
    - 20-50 samples: 0.7 confidence
    - 50-100 samples: 0.85 confidence
    - 100+ samples: 1.0 confidence

Usage:
    from pattern_extraction import (
        build_pattern_profile,
        build_global_pattern_profile,
        PatternProfileCache,
        get_pattern_score,
        warm_pattern_cache,
    )

    # Build profile for a specific creator
    profile = build_pattern_profile(conn, creator_id)

    # Get score for a caption's attributes
    score = get_pattern_score(profile, "sextape", "playful", "question")

    # Use cached profiles
    cache = PatternProfileCache()
    cache.set(creator_id, profile)
    cached_profile = cache.get(creator_id)

Example:
    >>> from database import get_connection
    >>> with get_connection() as conn:
    ...     profile = build_pattern_profile(conn, "creator_123")
    ...     print(f"Patterns: {len(profile.combined_patterns)}")
    ...     print(f"Confidence: {profile.confidence}")
    Patterns: 45
    Confidence: 0.85
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from models import PatternProfile, PatternStats

__all__ = [
    "build_pattern_profile",
    "build_global_pattern_profile",
    "PatternProfileCache",
    "get_pattern_score",
    "warm_pattern_cache",
    "GLOBAL_PROFILE_DISCOUNT",
    "MIN_SAMPLES_FOR_CREATOR_PROFILE",
    "MIN_SAMPLES_FOR_COMBINED_PATTERN",
]

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

GLOBAL_PROFILE_DISCOUNT: float = 0.7
"""Discount factor applied to global fallback pattern scores."""

MIN_SAMPLES_FOR_CREATOR_PROFILE: int = 20
"""Minimum sends required for creator-specific profile (else use global)."""

MIN_SAMPLES_FOR_COMBINED_PATTERN: int = 3
"""Minimum samples required for a combined pattern to be valid."""

LOOKBACK_DAYS: int = 90
"""Number of days to look back for pattern extraction."""

BASE_PATTERN_SCORE: float = 30.0
"""Default score when no pattern data is available."""

# Confidence thresholds
CONFIDENCE_THRESHOLD_LOW: int = 20
CONFIDENCE_THRESHOLD_MID: int = 50
CONFIDENCE_THRESHOLD_HIGH: int = 100


# =============================================================================
# CONFIDENCE CALCULATION
# =============================================================================


def _calculate_confidence(sample_count: int) -> float:
    """
    Calculate confidence score based on sample count.

    Confidence tiers:
        - <20 samples: 0.5 (minimum confidence)
        - 20-50 samples: 0.7 (moderate confidence)
        - 50-100 samples: 0.85 (good confidence)
        - 100+ samples: 1.0 (high confidence)

    Args:
        sample_count: Number of data points used for pattern extraction.

    Returns:
        Confidence score between 0.5 and 1.0.

    Example:
        >>> _calculate_confidence(10)
        0.5
        >>> _calculate_confidence(75)
        0.85
        >>> _calculate_confidence(150)
        1.0
    """
    if sample_count < CONFIDENCE_THRESHOLD_LOW:
        return 0.5
    elif sample_count < CONFIDENCE_THRESHOLD_MID:
        return 0.7
    elif sample_count < CONFIDENCE_THRESHOLD_HIGH:
        return 0.85
    else:
        return 1.0


# =============================================================================
# PATTERN EXTRACTION QUERIES
# =============================================================================
#
# Query Performance Notes:
# ========================
# These queries are optimized for the following indexes:
#
# For creator-specific queries:
#   - idx_mass_messages_creator_time ON mass_messages(creator_id, sending_time)
#     Provides efficient filtering by creator + time range
#
# For global (portfolio-wide) queries:
#   - idx_mm_earnings ON mass_messages(earnings DESC)
#     Used when no creator filter; scans messages with earnings > 0
#
# Join optimization:
#   - caption_bank joined via caption_id (INTEGER PRIMARY KEY)
#   - content_types joined via content_type_id (INTEGER PRIMARY KEY)
#   - Both use primary key lookups (very efficient)
#
# Performance targets (66,826 mass_messages, 19,590 captions):
#   - Creator-specific pattern query: < 5ms
#   - Global pattern query: < 20ms
#   - Total sample count: < 1ms
#
# To create recommended indexes, run:
#   sqlite3 $EROS_DATABASE_PATH < assets/sql/fresh_selection_indexes.sql
# =============================================================================


def _extract_combined_patterns(
    conn: sqlite3.Connection,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract combined patterns (content_type + tone + hook_type).

    Queries the mass_messages table joined with caption_bank and content_types
    to aggregate earnings by the combination of content_type, tone, and
    hook_type (emoji_style). Only patterns with 3+ samples are returned.

    Args:
        conn: Database connection with row_factory set.
        creator_id: Optional creator UUID. If None, extracts global patterns.

    Returns:
        List of dicts with keys: content_type, tone, hook_type,
        avg_earnings, sample_count.

    Example:
        >>> patterns = _extract_combined_patterns(conn, "creator_123")
        >>> patterns[0]
        {'content_type': 'sextape', 'tone': 'playful', 'hook_type': 'heavy',
         'avg_earnings': 45.50, 'sample_count': 23}
    """
    base_query = """
        SELECT
            ct.type_name AS content_type,
            cb.tone,
            cb.emoji_style AS hook_type,
            AVG(mm.earnings) AS avg_earnings,
            COUNT(*) AS sample_count
        FROM mass_messages mm
        JOIN caption_bank cb ON mm.caption_id = cb.caption_id
        JOIN content_types ct ON mm.content_type_id = ct.content_type_id
        WHERE mm.sending_time >= datetime('now', '-{lookback} days')
          AND mm.earnings > 0
          AND cb.tone IS NOT NULL
          AND cb.emoji_style IS NOT NULL
          {creator_filter}
        GROUP BY ct.type_name, cb.tone, cb.emoji_style
        HAVING COUNT(*) >= {min_samples}
        ORDER BY avg_earnings DESC
    """.format(
        lookback=LOOKBACK_DAYS,
        creator_filter="AND mm.creator_id = :creator_id" if creator_id else "",
        min_samples=MIN_SAMPLES_FOR_COMBINED_PATTERN,
    )

    params: dict[str, Any] = {}
    if creator_id:
        params["creator_id"] = creator_id

    cursor = conn.execute(base_query, params)
    results: list[dict[str, Any]] = []

    for row in cursor.fetchall():
        results.append({
            "content_type": row["content_type"] or "",
            "tone": row["tone"] or "",
            "hook_type": row["hook_type"] or "",
            "avg_earnings": float(row["avg_earnings"] or 0.0),
            "sample_count": int(row["sample_count"] or 0),
        })

    return results


def _extract_content_type_patterns(
    conn: sqlite3.Connection,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract content type only patterns (Tier 2 fallback).

    Args:
        conn: Database connection with row_factory set.
        creator_id: Optional creator UUID. If None, extracts global patterns.

    Returns:
        List of dicts with keys: content_type, avg_earnings, sample_count.
    """
    query = """
        SELECT
            ct.type_name AS content_type,
            AVG(mm.earnings) AS avg_earnings,
            COUNT(*) AS sample_count
        FROM mass_messages mm
        JOIN content_types ct ON mm.content_type_id = ct.content_type_id
        WHERE mm.sending_time >= datetime('now', '-{lookback} days')
          AND mm.earnings > 0
          {creator_filter}
        GROUP BY ct.type_name
        HAVING COUNT(*) >= 1
        ORDER BY avg_earnings DESC
    """.format(
        lookback=LOOKBACK_DAYS,
        creator_filter="AND mm.creator_id = :creator_id" if creator_id else "",
    )

    params: dict[str, Any] = {}
    if creator_id:
        params["creator_id"] = creator_id

    cursor = conn.execute(query, params)
    results: list[dict[str, Any]] = []

    for row in cursor.fetchall():
        results.append({
            "content_type": row["content_type"] or "",
            "avg_earnings": float(row["avg_earnings"] or 0.0),
            "sample_count": int(row["sample_count"] or 0),
        })

    return results


def _extract_tone_patterns(
    conn: sqlite3.Connection,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract tone only patterns (Tier 2 fallback).

    Args:
        conn: Database connection with row_factory set.
        creator_id: Optional creator UUID. If None, extracts global patterns.

    Returns:
        List of dicts with keys: tone, avg_earnings, sample_count.
    """
    query = """
        SELECT
            cb.tone,
            AVG(mm.earnings) AS avg_earnings,
            COUNT(*) AS sample_count
        FROM mass_messages mm
        JOIN caption_bank cb ON mm.caption_id = cb.caption_id
        WHERE mm.sending_time >= datetime('now', '-{lookback} days')
          AND mm.earnings > 0
          AND cb.tone IS NOT NULL
          {creator_filter}
        GROUP BY cb.tone
        HAVING COUNT(*) >= 1
        ORDER BY avg_earnings DESC
    """.format(
        lookback=LOOKBACK_DAYS,
        creator_filter="AND mm.creator_id = :creator_id" if creator_id else "",
    )

    params: dict[str, Any] = {}
    if creator_id:
        params["creator_id"] = creator_id

    cursor = conn.execute(query, params)
    results: list[dict[str, Any]] = []

    for row in cursor.fetchall():
        results.append({
            "tone": row["tone"] or "",
            "avg_earnings": float(row["avg_earnings"] or 0.0),
            "sample_count": int(row["sample_count"] or 0),
        })

    return results


def _extract_hook_patterns(
    conn: sqlite3.Connection,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract hook type (emoji_style) only patterns (Tier 2 fallback).

    Args:
        conn: Database connection with row_factory set.
        creator_id: Optional creator UUID. If None, extracts global patterns.

    Returns:
        List of dicts with keys: hook_type, avg_earnings, sample_count.
    """
    query = """
        SELECT
            cb.emoji_style AS hook_type,
            AVG(mm.earnings) AS avg_earnings,
            COUNT(*) AS sample_count
        FROM mass_messages mm
        JOIN caption_bank cb ON mm.caption_id = cb.caption_id
        WHERE mm.sending_time >= datetime('now', '-{lookback} days')
          AND mm.earnings > 0
          AND cb.emoji_style IS NOT NULL
          {creator_filter}
        GROUP BY cb.emoji_style
        HAVING COUNT(*) >= 1
        ORDER BY avg_earnings DESC
    """.format(
        lookback=LOOKBACK_DAYS,
        creator_filter="AND mm.creator_id = :creator_id" if creator_id else "",
    )

    params: dict[str, Any] = {}
    if creator_id:
        params["creator_id"] = creator_id

    cursor = conn.execute(query, params)
    results: list[dict[str, Any]] = []

    for row in cursor.fetchall():
        results.append({
            "hook_type": row["hook_type"] or "",
            "avg_earnings": float(row["avg_earnings"] or 0.0),
            "sample_count": int(row["sample_count"] or 0),
        })

    return results


def _get_total_sample_count(
    conn: sqlite3.Connection,
    creator_id: str | None = None,
) -> int:
    """
    Get total number of mass messages with earnings for a creator.

    Args:
        conn: Database connection.
        creator_id: Optional creator UUID. If None, counts all messages.

    Returns:
        Total count of messages with earnings > 0.
    """
    query = """
        SELECT COUNT(*) AS total
        FROM mass_messages
        WHERE sending_time >= datetime('now', '-{lookback} days')
          AND earnings > 0
          {creator_filter}
    """.format(
        lookback=LOOKBACK_DAYS,
        creator_filter="AND creator_id = :creator_id" if creator_id else "",
    )

    params: dict[str, Any] = {}
    if creator_id:
        params["creator_id"] = creator_id

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    return int(row["total"]) if row else 0


# =============================================================================
# NORMALIZED SCORE CALCULATION
# =============================================================================


def _calculate_normalized_scores(
    patterns: list[dict[str, Any]],
    earnings_key: str = "avg_earnings",
) -> dict[str, float]:
    """
    Calculate percentile-based normalized scores for patterns.

    Ranks patterns by avg_earnings and converts to percentile scores (0-100).
    Higher scores indicate better-performing patterns.

    Args:
        patterns: List of pattern dicts with avg_earnings.
        earnings_key: Key to use for earnings lookup.

    Returns:
        Dict mapping pattern identifier to normalized score (0-100).

    Example:
        >>> patterns = [
        ...     {"content_type": "sextape", "avg_earnings": 50.0},
        ...     {"content_type": "solo", "avg_earnings": 30.0},
        ... ]
        >>> scores = _calculate_normalized_scores(patterns)
        >>> scores["sextape"]
        100.0
        >>> scores["solo"]
        50.0
    """
    if not patterns:
        return {}

    # Sort by earnings ascending for percentile calculation
    sorted_patterns = sorted(patterns, key=lambda p: p.get(earnings_key, 0))
    total = len(sorted_patterns)

    scores: dict[str, float] = {}
    for rank, pattern in enumerate(sorted_patterns, 1):
        # Percentile rank: (rank / total) * 100
        percentile = (rank / total) * 100

        # Build key based on available fields
        if "content_type" in pattern and "tone" in pattern and "hook_type" in pattern:
            key = f"{pattern['content_type']}|{pattern['tone']}|{pattern['hook_type']}"
        elif "content_type" in pattern:
            key = pattern["content_type"]
        elif "tone" in pattern:
            key = pattern["tone"]
        elif "hook_type" in pattern:
            key = pattern["hook_type"]
        else:
            continue

        scores[key] = percentile

    return scores


# =============================================================================
# MAIN PROFILE BUILDING FUNCTIONS
# =============================================================================


def build_pattern_profile(
    conn: sqlite3.Connection,
    creator_id: str,
) -> PatternProfile:
    """
    Build a PatternProfile from historical mass_message performance.

    Two-tier pattern extraction:
    - Tier 1: Combined patterns (content_type + tone + hook_type) requiring 3+ samples
    - Tier 2: Individual attribute fallbacks when combined patterns are sparse

    If the creator has fewer than 20 sends with earnings, is_global_fallback
    is set to True to indicate that global patterns should be preferred.

    Args:
        conn: Database connection with row_factory set.
        creator_id: Creator UUID to build profile for.

    Returns:
        PatternProfile with pattern statistics and confidence scoring.

    Example:
        >>> profile = build_pattern_profile(conn, "creator_123")
        >>> print(f"Combined patterns: {len(profile.combined_patterns)}")
        >>> print(f"Confidence: {profile.confidence}")
        >>> if profile.is_global_fallback:
        ...     print("Using global fallback due to sparse data")
    """
    logger.debug(f"Building pattern profile for creator {creator_id}")

    # Get total sample count to determine if we need global fallback
    total_samples = _get_total_sample_count(conn, creator_id)
    is_sparse = total_samples < MIN_SAMPLES_FOR_CREATOR_PROFILE

    if is_sparse:
        logger.info(
            f"Creator {creator_id} has {total_samples} samples, "
            f"flagging for global fallback (minimum: {MIN_SAMPLES_FOR_CREATOR_PROFILE})"
        )

    # Extract combined patterns (Tier 1)
    combined_raw = _extract_combined_patterns(conn, creator_id)
    combined_scores = _calculate_normalized_scores(combined_raw)

    combined_patterns: dict[str, PatternStats] = {}
    for pattern in combined_raw:
        key = f"{pattern['content_type']}|{pattern['tone']}|{pattern['hook_type']}"
        normalized_score = combined_scores.get(key, 50.0)
        combined_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    # Extract individual patterns (Tier 2)
    content_type_raw = _extract_content_type_patterns(conn, creator_id)
    ct_scores = _calculate_normalized_scores(content_type_raw)
    content_type_patterns: dict[str, PatternStats] = {}
    for pattern in content_type_raw:
        key = pattern["content_type"]
        normalized_score = ct_scores.get(key, 50.0)
        content_type_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    tone_raw = _extract_tone_patterns(conn, creator_id)
    tone_scores = _calculate_normalized_scores(tone_raw)
    tone_patterns: dict[str, PatternStats] = {}
    for pattern in tone_raw:
        key = pattern["tone"]
        normalized_score = tone_scores.get(key, 50.0)
        tone_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    hook_raw = _extract_hook_patterns(conn, creator_id)
    hook_scores = _calculate_normalized_scores(hook_raw)
    hook_patterns: dict[str, PatternStats] = {}
    for pattern in hook_raw:
        key = pattern["hook_type"]
        normalized_score = hook_scores.get(key, 50.0)
        hook_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    # Calculate overall confidence
    confidence = _calculate_confidence(total_samples)

    logger.info(
        f"Pattern profile for {creator_id}: "
        f"{len(combined_patterns)} combined, "
        f"{len(content_type_patterns)} content_type, "
        f"{len(tone_patterns)} tone, "
        f"{len(hook_patterns)} hook patterns | "
        f"samples={total_samples}, confidence={confidence}"
    )

    return PatternProfile(
        creator_id=creator_id,
        combined_patterns=combined_patterns,
        content_type_patterns=content_type_patterns,
        tone_patterns=tone_patterns,
        hook_patterns=hook_patterns,
        sample_count=total_samples,
        confidence=confidence,
        is_global_fallback=is_sparse,
        cached_at=datetime.now(),
    )


def build_global_pattern_profile(conn: sqlite3.Connection) -> PatternProfile:
    """
    Build a global PatternProfile from all creators' data.

    Used as fallback for new creators with sparse data. All normalized
    scores are discounted by GLOBAL_PROFILE_DISCOUNT (0.7x) to account
    for the fact that global patterns may not perfectly match any
    individual creator's audience.

    Args:
        conn: Database connection with row_factory set.

    Returns:
        PatternProfile with is_global_fallback=True and discounted scores.

    Example:
        >>> global_profile = build_global_pattern_profile(conn)
        >>> print(f"Global patterns: {len(global_profile.combined_patterns)}")
        >>> print(f"Is fallback: {global_profile.is_global_fallback}")
        Global patterns: 150
        Is fallback: True
    """
    logger.debug("Building global pattern profile")

    # Get total sample count (all creators)
    total_samples = _get_total_sample_count(conn)

    # Extract combined patterns (Tier 1) - no creator filter
    combined_raw = _extract_combined_patterns(conn)
    combined_scores = _calculate_normalized_scores(combined_raw)

    combined_patterns: dict[str, PatternStats] = {}
    for pattern in combined_raw:
        key = f"{pattern['content_type']}|{pattern['tone']}|{pattern['hook_type']}"
        # Apply global discount to normalized score
        normalized_score = combined_scores.get(key, 50.0) * GLOBAL_PROFILE_DISCOUNT
        combined_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    # Extract individual patterns (Tier 2)
    content_type_raw = _extract_content_type_patterns(conn)
    ct_scores = _calculate_normalized_scores(content_type_raw)
    content_type_patterns: dict[str, PatternStats] = {}
    for pattern in content_type_raw:
        key = pattern["content_type"]
        normalized_score = ct_scores.get(key, 50.0) * GLOBAL_PROFILE_DISCOUNT
        content_type_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    tone_raw = _extract_tone_patterns(conn)
    tone_scores = _calculate_normalized_scores(tone_raw)
    tone_patterns: dict[str, PatternStats] = {}
    for pattern in tone_raw:
        key = pattern["tone"]
        normalized_score = tone_scores.get(key, 50.0) * GLOBAL_PROFILE_DISCOUNT
        tone_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    hook_raw = _extract_hook_patterns(conn)
    hook_scores = _calculate_normalized_scores(hook_raw)
    hook_patterns: dict[str, PatternStats] = {}
    for pattern in hook_raw:
        key = pattern["hook_type"]
        normalized_score = hook_scores.get(key, 50.0) * GLOBAL_PROFILE_DISCOUNT
        hook_patterns[key] = PatternStats(
            avg_earnings=pattern["avg_earnings"],
            sample_count=pattern["sample_count"],
            normalized_score=normalized_score,
        )

    # Calculate overall confidence
    confidence = _calculate_confidence(total_samples)

    logger.info(
        f"Global pattern profile: "
        f"{len(combined_patterns)} combined, "
        f"{len(content_type_patterns)} content_type, "
        f"{len(tone_patterns)} tone, "
        f"{len(hook_patterns)} hook patterns | "
        f"samples={total_samples}, confidence={confidence}"
    )

    return PatternProfile(
        creator_id="GLOBAL",
        combined_patterns=combined_patterns,
        content_type_patterns=content_type_patterns,
        tone_patterns=tone_patterns,
        hook_patterns=hook_patterns,
        sample_count=total_samples,
        confidence=confidence,
        is_global_fallback=True,
        cached_at=datetime.now(),
    )


# =============================================================================
# PATTERN SCORE LOOKUP
# =============================================================================


def get_pattern_score(
    profile: PatternProfile,
    content_type: str,
    tone: str,
    hook_type: str,
) -> float:
    """
    Get pattern score for a caption's attributes.

    Lookup order:
    1. Combined pattern key: "content_type|tone|hook_type"
    2. Fallback to individual attributes (average of available)
    3. Return BASE_PATTERN_SCORE (30.0) if no pattern data

    Args:
        profile: PatternProfile to lookup scores in.
        content_type: Content type name (e.g., "sextape", "solo").
        tone: Caption tone (e.g., "playful", "seductive").
        hook_type: Hook type / emoji_style (e.g., "heavy", "moderate").

    Returns:
        Pattern score between 0-100, or BASE_PATTERN_SCORE if no data.

    Example:
        >>> score = get_pattern_score(profile, "sextape", "playful", "heavy")
        >>> print(f"Pattern score: {score:.1f}")
        Pattern score: 78.5

        >>> # Fallback when combined pattern not found
        >>> score = get_pattern_score(profile, "new_type", "playful", "moderate")
        >>> print(f"Fallback score: {score:.1f}")  # Average of individual patterns
        Fallback score: 55.2
    """
    # Handle None/empty values
    content_type = content_type or ""
    tone = tone or ""
    hook_type = hook_type or ""

    # Try combined pattern first (Tier 1)
    combined_key = f"{content_type}|{tone}|{hook_type}"
    if combined_key in profile.combined_patterns:
        return profile.combined_patterns[combined_key].normalized_score

    # Fall back to individual patterns (Tier 2)
    scores: list[float] = []

    if content_type and content_type in profile.content_type_patterns:
        scores.append(profile.content_type_patterns[content_type].normalized_score)

    if tone and tone in profile.tone_patterns:
        scores.append(profile.tone_patterns[tone].normalized_score)

    if hook_type and hook_type in profile.hook_patterns:
        scores.append(profile.hook_patterns[hook_type].normalized_score)

    # Return average of available individual patterns
    if scores:
        return sum(scores) / len(scores)

    # No pattern data available
    return BASE_PATTERN_SCORE


# =============================================================================
# CACHE IMPLEMENTATION
# =============================================================================


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL tracking."""

    profile: PatternProfile
    expires_at: datetime


class PatternProfileCache:
    """
    Thread-safe LRU cache for PatternProfiles with TTL expiration.

    Features:
    - Max 100 profiles cached (configurable)
    - 24-hour TTL per profile (configurable)
    - Thread-safe access via threading.Lock
    - Automatic eviction of expired/LRU entries
    - Manual invalidation support

    Example:
        >>> cache = PatternProfileCache(max_size=50, ttl_hours=12)
        >>> cache.set("creator_123", profile)
        >>> cached = cache.get("creator_123")
        >>> if cached is None:
        ...     # Cache miss or expired
        ...     cached = build_pattern_profile(conn, "creator_123")
        ...     cache.set("creator_123", cached)
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_hours: int = 24,
    ) -> None:
        """
        Initialize the PatternProfileCache.

        Args:
            max_size: Maximum number of profiles to cache.
            ttl_hours: Hours until a cached profile expires.
        """
        self._max_size = max_size
        self._ttl = timedelta(hours=ttl_hours)
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, creator_id: str) -> PatternProfile | None:
        """
        Get profile if cached and not expired.

        If the profile exists but is expired, it is removed from cache
        and None is returned.

        Args:
            creator_id: Creator UUID or "GLOBAL" for global profile.

        Returns:
            Cached PatternProfile if valid, None otherwise.

        Example:
            >>> profile = cache.get("creator_123")
            >>> if profile is None:
            ...     profile = build_pattern_profile(conn, "creator_123")
            ...     cache.set("creator_123", profile)
        """
        with self._lock:
            if creator_id not in self._cache:
                return None

            entry = self._cache[creator_id]

            # Check expiration
            if datetime.now() > entry.expires_at:
                del self._cache[creator_id]
                logger.debug(f"Cache entry expired for {creator_id}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(creator_id)
            logger.debug(f"Cache hit for {creator_id}")
            return entry.profile

    def set(self, creator_id: str, profile: PatternProfile) -> None:
        """
        Cache a profile, evicting LRU if at capacity.

        If the cache is at max capacity, the least recently used
        entry is evicted before adding the new profile.

        Args:
            creator_id: Creator UUID or "GLOBAL" for global profile.
            profile: PatternProfile to cache.

        Example:
            >>> profile = build_pattern_profile(conn, "creator_123")
            >>> cache.set("creator_123", profile)
        """
        with self._lock:
            # Remove if already exists (to update position)
            if creator_id in self._cache:
                del self._cache[creator_id]

            # Evict LRU entries if at capacity
            while len(self._cache) >= self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(f"Evicted LRU cache entry: {evicted_key}")

            # Add new entry
            expires_at = datetime.now() + self._ttl
            self._cache[creator_id] = _CacheEntry(
                profile=profile,
                expires_at=expires_at,
            )
            logger.debug(f"Cached profile for {creator_id}, expires at {expires_at}")

    def invalidate(self, creator_id: str) -> None:
        """
        Remove a profile from cache.

        Safe to call even if the profile is not cached.

        Args:
            creator_id: Creator UUID or "GLOBAL" to invalidate.

        Example:
            >>> cache.invalidate("creator_123")  # Remove specific creator
            >>> cache.invalidate("GLOBAL")  # Remove global profile
        """
        with self._lock:
            if creator_id in self._cache:
                del self._cache[creator_id]
                logger.debug(f"Invalidated cache entry for {creator_id}")

    def clear(self) -> None:
        """
        Clear all cached profiles.

        Example:
            >>> cache.clear()  # Remove all cached profiles
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} entries from pattern profile cache")

    def stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics including size, max_size,
            ttl_hours, and list of cached creator_ids.

        Example:
            >>> stats = cache.stats()
            >>> print(f"Cache size: {stats['size']}/{stats['max_size']}")
        """
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_hours": self._ttl.total_seconds() / 3600,
                "cached_creators": list(self._cache.keys()),
            }


# =============================================================================
# CACHE WARMING
# =============================================================================


def warm_pattern_cache(
    conn: sqlite3.Connection,
    cache: PatternProfileCache,
    creator_ids: list[str] | None = None,
) -> dict[str, PatternProfile]:
    """
    Pre-load pattern profiles for multiple creators.

    If creator_ids is None, loads profiles for all active creators
    in the database. Also loads the global profile.

    Args:
        conn: Database connection with row_factory set.
        cache: PatternProfileCache to populate.
        creator_ids: Optional list of creator UUIDs. If None, loads all active.

    Returns:
        Dictionary mapping creator_id to loaded PatternProfile.

    Example:
        >>> cache = PatternProfileCache()
        >>> profiles = warm_pattern_cache(conn, cache)
        >>> print(f"Warmed {len(profiles)} profiles")

        >>> # Warm specific creators only
        >>> profiles = warm_pattern_cache(conn, cache, ["creator_1", "creator_2"])
    """
    logger.info("Warming pattern profile cache...")

    # Get creator IDs if not provided
    if creator_ids is None:
        cursor = conn.execute(
            "SELECT creator_id FROM creators WHERE is_active = 1"
        )
        creator_ids = [row["creator_id"] for row in cursor.fetchall()]

    loaded: dict[str, PatternProfile] = {}

    # Load individual creator profiles
    for creator_id in creator_ids:
        try:
            profile = build_pattern_profile(conn, creator_id)
            cache.set(creator_id, profile)
            loaded[creator_id] = profile
        except Exception as e:
            logger.warning(f"Failed to build profile for {creator_id}: {e}")

    # Load global profile
    try:
        global_profile = build_global_pattern_profile(conn)
        cache.set("GLOBAL", global_profile)
        loaded["GLOBAL"] = global_profile
    except Exception as e:
        logger.warning(f"Failed to build global profile: {e}")

    logger.info(
        f"Warmed pattern cache with {len(loaded)} profiles "
        f"({len(creator_ids)} creators + global)"
    )

    return loaded


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """CLI entry point for pattern extraction testing."""
    import argparse
    import json

    from database import get_connection

    parser = argparse.ArgumentParser(
        description="Extract and display pattern profiles for creators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pattern_extraction.py --creator creator_uuid
    python pattern_extraction.py --global
    python pattern_extraction.py --creator creator_uuid --format json
    python pattern_extraction.py --warm-cache --output cache_stats.json
        """,
    )

    parser.add_argument("--creator", "-c", help="Creator UUID to build profile for")
    parser.add_argument(
        "--global", "-g", dest="global_profile", action="store_true",
        help="Build global pattern profile"
    )
    parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--warm-cache", action="store_true",
        help="Warm cache for all active creators"
    )
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument(
        "--benchmark", "-b", action="store_true",
        help="Run performance benchmark on pattern extraction queries"
    )

    args = parser.parse_args()

    with get_connection() as conn:
        if args.benchmark:
            import time

            # Get a sample creator for benchmarking
            cursor = conn.execute(
                "SELECT creator_id FROM creators WHERE is_active = 1 LIMIT 1"
            )
            row = cursor.fetchone()
            sample_creator = row["creator_id"] if row else None

            print("=" * 60)
            print("Pattern Extraction Query Benchmark")
            print("=" * 60)

            def benchmark_query(name: str, func, *func_args, iterations: int = 5):
                times = []
                for _ in range(iterations):
                    start = time.perf_counter()
                    result = func(*func_args)
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
                avg_time = sum(times) / len(times)
                status = "OK" if avg_time < 100 else "SLOW"
                print(f"{name:<35} {avg_time:>8.2f}ms  {status}")
                return avg_time

            if sample_creator:
                benchmark_query(
                    "Combined patterns (creator)",
                    _extract_combined_patterns, conn, sample_creator
                )
                benchmark_query(
                    "Content type patterns (creator)",
                    _extract_content_type_patterns, conn, sample_creator
                )
                benchmark_query(
                    "Tone patterns (creator)",
                    _extract_tone_patterns, conn, sample_creator
                )
                benchmark_query(
                    "Hook patterns (creator)",
                    _extract_hook_patterns, conn, sample_creator
                )
                benchmark_query(
                    "Total sample count (creator)",
                    _get_total_sample_count, conn, sample_creator
                )
                benchmark_query(
                    "Full profile build (creator)",
                    build_pattern_profile, conn, sample_creator
                )

            print("-" * 60)
            benchmark_query(
                "Combined patterns (global)",
                _extract_combined_patterns, conn, None
            )
            benchmark_query(
                "Content type patterns (global)",
                _extract_content_type_patterns, conn, None
            )
            benchmark_query(
                "Full profile build (global)",
                build_global_pattern_profile, conn
            )

            print("=" * 60)
            print("Performance targets: < 100ms per query")
            return

        if args.warm_cache:
            cache = PatternProfileCache()
            profiles = warm_pattern_cache(conn, cache)

            output_data = {
                "warmed_count": len(profiles),
                "creator_ids": list(profiles.keys()),
                "cache_stats": cache.stats(),
            }

            if args.format == "json":
                output = json.dumps(output_data, indent=2, default=str)
            else:
                output = (
                    f"Warmed {len(profiles)} profiles\n"
                    f"Cache stats: {cache.stats()}"
                )

        elif args.global_profile:
            profile = build_global_pattern_profile(conn)

            if args.format == "json":
                output = json.dumps({
                    "creator_id": profile.creator_id,
                    "sample_count": profile.sample_count,
                    "confidence": profile.confidence,
                    "is_global_fallback": profile.is_global_fallback,
                    "combined_patterns_count": len(profile.combined_patterns),
                    "content_type_patterns_count": len(profile.content_type_patterns),
                    "tone_patterns_count": len(profile.tone_patterns),
                    "hook_patterns_count": len(profile.hook_patterns),
                    "top_combined_patterns": {
                        k: {
                            "avg_earnings": v.avg_earnings,
                            "sample_count": v.sample_count,
                            "normalized_score": v.normalized_score,
                        }
                        for k, v in sorted(
                            profile.combined_patterns.items(),
                            key=lambda x: x[1].normalized_score,
                            reverse=True,
                        )[:10]
                    },
                }, indent=2)
            else:
                output = (
                    f"Global Pattern Profile\n"
                    f"=====================\n"
                    f"Sample Count: {profile.sample_count}\n"
                    f"Confidence: {profile.confidence}\n"
                    f"Combined Patterns: {len(profile.combined_patterns)}\n"
                    f"Content Type Patterns: {len(profile.content_type_patterns)}\n"
                    f"Tone Patterns: {len(profile.tone_patterns)}\n"
                    f"Hook Patterns: {len(profile.hook_patterns)}\n"
                )

        elif args.creator:
            profile = build_pattern_profile(conn, args.creator)

            if args.format == "json":
                output = json.dumps({
                    "creator_id": profile.creator_id,
                    "sample_count": profile.sample_count,
                    "confidence": profile.confidence,
                    "is_global_fallback": profile.is_global_fallback,
                    "combined_patterns_count": len(profile.combined_patterns),
                    "content_type_patterns_count": len(profile.content_type_patterns),
                    "tone_patterns_count": len(profile.tone_patterns),
                    "hook_patterns_count": len(profile.hook_patterns),
                    "top_combined_patterns": {
                        k: {
                            "avg_earnings": v.avg_earnings,
                            "sample_count": v.sample_count,
                            "normalized_score": v.normalized_score,
                        }
                        for k, v in sorted(
                            profile.combined_patterns.items(),
                            key=lambda x: x[1].normalized_score,
                            reverse=True,
                        )[:10]
                    },
                }, indent=2)
            else:
                output = (
                    f"Pattern Profile for {args.creator}\n"
                    f"{'=' * 40}\n"
                    f"Sample Count: {profile.sample_count}\n"
                    f"Confidence: {profile.confidence}\n"
                    f"Global Fallback: {profile.is_global_fallback}\n"
                    f"Combined Patterns: {len(profile.combined_patterns)}\n"
                    f"Content Type Patterns: {len(profile.content_type_patterns)}\n"
                    f"Tone Patterns: {len(profile.tone_patterns)}\n"
                    f"Hook Patterns: {len(profile.hook_patterns)}\n"
                )

        else:
            parser.error("Must specify --creator, --global, or --warm-cache")
            return

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Output written to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
